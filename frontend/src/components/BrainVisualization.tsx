"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export type MeshType = "inflated" | "pial";

export interface RegionClickInfo {
  /** HCP-MMP1 ROI short name, e.g. "A1" */
  roi: string;
  /** Human-readable name, e.g. "Primary Auditory Cortex" */
  fullName: string;
  /** Functional category: visual | auditory | language | dorsal_attention | mpfc_valuation | multisensory | other */
  category: string;
  /** Hemisphere: "lh" | "rh" */
  hemi: "lh" | "rh";
  /** Activation value at this vertex (raw overlay value, NaN if no overlay) */
  activation: number;
  /** Vertex index within the hemisphere mesh */
  vertexIndex: number;
}

interface HcpAtlas {
  lh: string[];
  rh: string[];
  roi_info: Record<string, { full_name: string; category: string }>;
}

interface BrainVisualizationProps {
  /** Job ID — used to load the 4D GIFTI overlay */
  jobId?: string;
  /** Current timestep index (0-based) — drives frame4D switching */
  timestep?: number;
  /** Which surface mesh to render */
  meshType?: MeshType;
  /** When true the two hemispheres are split apart to show medial surfaces */
  isOpen?: boolean;
  /** Fired when the user clicks on a brain region (double-click triggers depth pick) */
  onRegionClick?: (info: RegionClickInfo) => void;
  /** Increment to snap the camera back to the canonical view */
  resetSignal?: number;
}

/**
 * Threshold below which activation values are transparent (shows gray mesh).
 * ~40th percentile of typical TRIBE v2 output so only hotspots light up.
 */
const CAL_MIN = 0.4;
const CAL_MAX = 0.85;

/**
 * Target fraction of the canvas the cortex bounding box should fill:
 * - Open brain view (inflated): 0.5
 * - Open brain view (normal): 0.6
 * - Closed (normal): 0.9
 * - Closed (inflated): 0.7
 */
function getFitTarget(type: MeshType, open: boolean): number {
  if (open) {
    return type === "inflated" ? 0.5 : 0.6;
  }
  return type === "inflated" ? 0.7 : 0.9;
}

/** In-memory cache for static hemisphere coordinates [leftPts, rightPts]. */
const coordsCache = new Map<string, [Float32Array, Float32Array]>();
/** In-memory cache for calculated camera scales per mode and canvas dimensions. */
const scaleCache = new Map<string, number>();

function meshUrl(side: "left" | "right", type: MeshType, open: boolean) {
  const base = type === "pial" ? "pial" : "infl";
  const suffix = open ? "_open" : "";
  return `/static/meshes/${base}_${side}${suffix}.gii`;
}

/**
 * Fetch and parse static mesh coordinates without touching NiiVue scene or overlays.
 * Cached in memory so subsequent switches resolve in 0 ms without network lag.
 */
async function fetchCoords(
  type: MeshType,
  open: boolean,
): Promise<[Float32Array, Float32Array]> {
  const key = `${type}-${open}`;
  const hit = coordsCache.get(key);
  if (hit) return hit;

  const { NVMeshLoaders } = await import("@niivue/niivue");
  const [leftBuf, rightBuf] = await Promise.all([
    fetch(meshUrl("left", type, open)).then((r) => {
      if (!r.ok) throw new Error(`Failed to load ${r.url}`);
      return r.arrayBuffer();
    }),
    fetch(meshUrl("right", type, open)).then((r) => {
      if (!r.ok) throw new Error(`Failed to load ${r.url}`);
      return r.arrayBuffer();
    }),
  ]);

  const [leftGii, rightGii] = await Promise.all([
    NVMeshLoaders.readGII(leftBuf),
    NVMeshLoaders.readGII(rightBuf),
  ]);

  if (!leftGii.positions || !rightGii.positions) {
    throw new Error("Invalid mesh geometry: missing vertex positions");
  }

  const coords: [Float32Array, Float32Array] = [
    new Float32Array(leftGii.positions),
    new Float32Array(rightGii.positions),
  ];
  coordsCache.set(key, coords);
  return coords;
}

/**
 * NiiVue draws 3D meshes at a fixed camera distance, so how big the cortex
 * appears depends on the mesh's extent and the canvas shape. Measure the
 * fraction of the canvas the mesh actually covers, so the view can be scaled
 * to a consistent size on every surface/layout combination.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function measureCoverage(nv: any): number {
  try {
    const gl = nv.gl;
    if (!gl) return 0;
    nv.drawScene();
    const w = gl.drawingBufferWidth;
    const h = gl.drawingBufferHeight;
    const px = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
    let minX = w;
    let maxX = -1;
    let minY = h;
    let maxY = -1;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (px[(y * w + x) * 4] > 70) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }
    if (maxX < 0) return 0;
    return Math.max((maxX - minX) / w, (maxY - minY) / h);
  } catch {
    return 0;
  }
}

/**
 * Scale the view so the cortex fills `target` of the panel. Measured at a
 * small probe scale first, so a clipping mesh reports its true extent.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function autoFit(nv: any, target = 0.8) {
  const PROBE = 0.4;
  nv.setScale(PROBE);
  const coverage = measureCoverage(nv);
  if (coverage <= 0.01) {
    nv.setScale(1);
    return;
  }
  const scale = (PROBE * target) / coverage;
  nv.setScale(Math.max(0.15, Math.min(2.5, scale)));
}

/**
 * Calculate the exact camera scale (volScaleMultiplier) needed to achieve
 * the target coverage ratio on the canvas, using cached values when available.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function computeScaleForMesh(
  nv: any,
  ptsList: Float32Array[],
  camera: { azimuth: number; elevation: number },
  target: number,
  cacheKey?: string,
): number {
  if (cacheKey && scaleCache.has(cacheKey)) {
    return scaleCache.get(cacheKey)!;
  }

  const gl = nv.gl;
  if (!gl || !nv.meshes || nv.meshes.length === 0) return 1;

  const curScale = nv.scene.volScaleMultiplier ?? 1;
  const curAz = nv.scene.renderAzimuth;
  const curEl = nv.scene.renderElevation;
  const curPts = nv.meshes.map((m: { pts: Float32Array }) => new Float32Array(m.pts));

  const PROBE = 0.4;
  nv.scene.volScaleMultiplier = PROBE;
  nv.scene.renderAzimuth = camera.azimuth;
  nv.scene.renderElevation = camera.elevation;
  for (let i = 0; i < nv.meshes.length && i < ptsList.length; i++) {
    nv.meshes[i].pts.set(ptsList[i]);
  }

  const coverage = measureCoverage(nv);

  for (let i = 0; i < nv.meshes.length && i < curPts.length; i++) {
    nv.meshes[i].pts.set(curPts[i]);
  }
  nv.scene.renderAzimuth = curAz;
  nv.scene.renderElevation = curEl;
  nv.scene.volScaleMultiplier = curScale;

  if (coverage <= 0.01) return curScale;
  const calculatedScale = (PROBE * target) / coverage;
  const finalScale = Math.max(0.15, Math.min(2.5, calculatedScale));

  if (cacheKey) {
    scaleCache.set(cacheKey, finalScale);
  }
  return finalScale;
}

export default function BrainVisualization({
  jobId,
  timestep = 0,
  meshType = "inflated",
  isOpen = false,
  onRegionClick,
  resetSignal,
}: BrainVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  /** Wrapper around the canvas — owns keyboard events (see below). */
  const hostRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nvRef = useRef<any>(null);
  /** Cache key for loaded geometry (meshType + isOpen) */
  const loadedGeoRef = useRef<string>("");
  /** Monotonically increasing version – guards against stale async ops */
  const versionRef = useRef(0);
  /** Currently running animation frame id */
  const animFrameRef = useRef<number>(0);
  /** Becomes true once NiiVue has loaded meshes with 4D overlay layers */
  const [layersReady, setLayersReady] = useState(false);
  /** True once the first mesh load resolves — drives the loading overlay */
  const [ready, setReady] = useState(false);
  /** Latest meshType value, readable from effects that must not re-run on it */
  const meshTypeRef = useRef(meshType);
  meshTypeRef.current = meshType;
  /** Latest isOpen value, readable from effects that must not re-run on it */
  const isOpenRef = useRef(isOpen);
  isOpenRef.current = isOpen;
  /** HCP atlas data — loaded once */
  const atlasRef = useRef<HcpAtlas | null>(null);
  /** Stable ref for the onRegionClick callback */
  const onRegionClickRef = useRef(onRegionClick);
  onRegionClickRef.current = onRegionClick;

  // ── Helpers ──────────────────────────────────────────────────────────

  function meshUrl(side: "left" | "right", type: MeshType, open: boolean) {
    const base = type === "pial" ? "pial" : "infl";
    const suffix = open ? "_open" : "";
    return `/static/meshes/${base}_${side}${suffix}.gii`;
  }

  function overlaySpec(hemi: "lh" | "rh", jid: string) {
    return {
      url: `/api/jobs/${jid}/overlay-4d/${hemi}`,
      name: `overlay_${hemi}.func.gii`,
      colormap: "hot",
      opacity: 0.9,
      cal_min: CAL_MIN,
      cal_max: CAL_MAX,
      cal_minNeg: 0,
      cal_maxNeg: 0,
      frame4D: 0,
    };
  }

  function buildSpecs(type: MeshType, jid: string | undefined, open: boolean) {
    return [
      {
        url: meshUrl("left", type, open),
        rgba255: [200, 200, 200, 255] as [number, number, number, number],
        layers: jid ? [overlaySpec("lh", jid)] : [],
      },
      {
        url: meshUrl("right", type, open),
        rgba255: [200, 200, 200, 255] as [number, number, number, number],
        layers: jid ? [overlaySpec("rh", jid)] : [],
      },
    ];
  }

  function cameraForMode(open: boolean) {
    return open
      ? { azimuth: 180, elevation: 0 }
      : { azimuth: 110, elevation: 10 };
  }

  function easeInOut(t: number) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function morphTo(
    nv: any,
    targetPts: Float32Array[],
    targetCamera: { azimuth: number; elevation: number },
    targetScale: number,
    ver: number,
    duration = 520,
  ) {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    const startPts = nv.meshes.map((m: { pts: Float32Array }) =>
      new Float32Array(m.pts),
    );
    const startAz = nv.scene.renderAzimuth;
    const startEl = nv.scene.renderElevation;
    const startScale = nv.scene.volScaleMultiplier ?? 1;
    const startTime = performance.now();

    function frame(now: number) {
      if (versionRef.current !== ver) return;
      const elapsed = now - startTime;
      const raw = Math.min(elapsed / duration, 1);
      const t = easeInOut(raw);

      for (let i = 0; i < nv.meshes.length && i < targetPts.length; i++) {
        const src = startPts[i];
        const dst = targetPts[i];
        const pts = nv.meshes[i].pts as Float32Array;
        for (let j = 0; j < pts.length; j++) {
          pts[j] = src[j] + t * (dst[j] - src[j]);
        }
      }

      nv.scene.renderAzimuth = startAz + t * (targetCamera.azimuth - startAz);
      nv.scene.renderElevation = startEl + t * (targetCamera.elevation - startEl);
      nv.scene.volScaleMultiplier = startScale + t * (targetScale - startScale);

      try {
        for (let i = 0; i < nv.meshes.length; i++) {
          nv.reverseFaces(i);
          nv.reverseFaces(i);
        }
      } catch {
        try { nv.updateGLVolume(); } catch { /* ignore */ }
      }
      nv.drawScene();

      if (raw < 1) {
        animFrameRef.current = requestAnimationFrame(frame);
      } else {
        animFrameRef.current = 0;
      }
    }

    animFrameRef.current = requestAnimationFrame(frame);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function animateCameraTo(
    nv: any,
    targetCamera: { azimuth: number; elevation: number },
    targetScale?: number,
    duration = 380,
  ) {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    const startAz = nv.scene.renderAzimuth;
    const startEl = nv.scene.renderElevation;
    const startScale = nv.scene.volScaleMultiplier ?? 1;
    const endScale = targetScale ?? startScale;
    const startTime = performance.now();

    function frame(now: number) {
      const raw = Math.min((now - startTime) / duration, 1);
      const t = easeInOut(raw);
      nv.scene.renderAzimuth = startAz + t * (targetCamera.azimuth - startAz);
      nv.scene.renderElevation = startEl + t * (targetCamera.elevation - startEl);
      nv.scene.volScaleMultiplier = startScale + t * (endScale - startScale);
      nv.drawScene();

      if (raw < 1) {
        animFrameRef.current = requestAnimationFrame(frame);
      } else {
        animFrameRef.current = 0;
      }
    }

    animFrameRef.current = requestAnimationFrame(frame);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function setCameraSnap(nv: any, open: boolean) {
    const c = cameraForMode(open);
    nv.scene.renderAzimuth = c.azimuth;
    nv.scene.renderElevation = c.elevation;
  }

  /**
   * Smoothly morph existing brain mesh coordinates, camera, and zoom scale in-place.
   * Keeps existing meshes and their 4D activation overlays intact so there is
   * zero blank pause, zero canvas teardown, and zero network re-downloading.
   *
   * Coordinates, rotation, and target zoom are all smoothly interpolated inside
   * the animation frame loop, preventing any post-animation resize snap.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async function morphGeometry(
    nv: any,
    type: MeshType,
    open: boolean,
    ver: number,
  ) {
    try {
      const targetPts = await fetchCoords(type, open);
      if (versionRef.current !== ver) return;

      const targetCam = cameraForMode(open);
      const targetRatio = getFitTarget(type, open);
      const gl = nv.gl;
      const dims = gl ? `${gl.drawingBufferWidth}x${gl.drawingBufferHeight}` : "";
      const cacheKey = `${type}-${open}-${dims}`;
      const targetScale = computeScaleForMesh(nv, targetPts, targetCam, targetRatio, cacheKey);

      morphTo(nv, targetPts, targetCam, targetScale, ver);
      loadedGeoRef.current = `${type}-${jobId ?? ""}-${open}`;
    } catch (err) {
      console.error("Failed to morph brain geometry:", err);
    }
  }

  /**
   * Full mesh load + 4D overlay setup.
   * Only called on initial mount or when jobId actually changes.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async function loadGeometry(
    nv: any,
    type: MeshType,
    jid: string | undefined,
    open: boolean,
    ver: number,
  ) {
    setLayersReady(false);

    for (const m of [...nv.meshes]) nv.removeMesh(m);
    await nv.loadMeshes(buildSpecs(type, jid, open));
    if (versionRef.current !== ver) return;

    // Cache the initial points in memory so future switches are instant
    if (nv.meshes.length >= 2) {
      coordsCache.set(`${type}-${open}`, [
        new Float32Array(nv.meshes[0].pts),
        new Float32Array(nv.meshes[1].pts),
      ]);
    }

    setCameraSnap(nv, open);
    autoFit(nv, getFitTarget(type, open));
    nv.drawScene();

    setLayersReady(!!(jid && nv.meshes.length >= 2));
    loadedGeoRef.current = `${type}-${jid ?? ""}-${open}`;
    setReady(true);

    // Warm up the remaining static coordinate sets in the background
    const allCombos: [MeshType, boolean][] = [
      ["inflated", false],
      ["inflated", true],
      ["pial", false],
      ["pial", true],
    ];
    for (const [t, o] of allCombos) {
      if (t !== type || o !== open) {
        fetchCoords(t, o).catch(() => {});
      }
    }
  }

  /**
   * Switch the 4D frame on both hemisphere overlays.
   * setMeshLayerProperty("frame4D", n) triggers NiiVue's internal
   * updateMesh → rebuilds the vertex colour texture from the colormap.
   */
  const setFrame = useCallback(
    async (frame: number) => {
      const nv = nvRef.current;
      if (!nv || nv.meshes.length < 2) return;
      for (let meshIdx = 0; meshIdx < 2; meshIdx++) {
        if (!nv.meshes[meshIdx].layers?.length) continue;
        try {
          await nv.setMeshLayerProperty(nv.meshes[meshIdx].id, 0, "frame4D", frame);
        } catch (e) {
          console.warn("frame4D update failed:", e);
        }
      }
    },
    [],
  );

  // ── Initialize NiiVue & load initial geometry ──────────────────────────
  useEffect(() => {
    if (!canvasRef.current) return;
    let cancelled = false;
    const ver = ++versionRef.current;
    let clickHandler: ((e: MouseEvent) => void) | null = null;

    (async () => {
      const { Niivue } = await import("@niivue/niivue");
      if (cancelled || !canvasRef.current) return;

      const nv = new Niivue({
        backColor: [0.04, 0.04, 0.05, 1],
        show3Dcrosshair: false,
        isOrientCube: false,
        isColorbar: false,
        // NiiVue's default maps wheel-up / pinch-out (deltaY < 0) to zoom OUT,
        // which is backwards from every map/canvas convention (and makes a Mac
        // trackpad pinch-out zoom out). Invert so deltaY < 0 zooms in.
        invertScrollDirection: true,
      });

      await nv.attachToCanvas(canvasRef.current);
      nv.setHighResolutionCapable(true);
      if (cancelled) return;
      nvRef.current = nv;

      // ── Load HCP atlas for click→region lookup ──────────────────────
      if (!atlasRef.current) {
        try {
          const resp = await fetch("/static/atlas/hcp_atlas.json");
          if (resp.ok) atlasRef.current = await resp.json();
        } catch {
          console.warn("Failed to load HCP atlas");
        }
      }

      // ── Click → region name handler ──────────────────────────────────
      // NiiVue fires onLocationChange after depth-pick (double-click on 3D mesh).
      // We also wire a single-click handler that triggers the same depth-pick path.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      nv.onLocationChange = (data: any) => {
        const atlas = atlasRef.current;
        const cb = onRegionClickRef.current;
        if (!atlas || !cb || !nv.meshes?.length) return;

        const mm = data.mm as number[];
        if (!mm || mm.every((v: number) => v === 0)) return;

        // Find nearest vertex on each hemisphere mesh, pick the closest
        let bestDist = Infinity;
        let bestVertex = -1;
        let bestMeshIdx = -1;

        for (let mi = 0; mi < Math.min(nv.meshes.length, 2); mi++) {
          // NiiVue's runtime matches the mesh by id, but its .d.ts types the
          // first argument as `number`; cast so the by-id lookup is preserved.
          const result = nv.indexNearestXYZmm(
            nv.meshes[mi].id as unknown as number,
            mm[0],
            mm[1],
            mm[2]
          );
          if (result && result[1] < bestDist) {
            bestDist = result[1];
            bestVertex = result[0];
            bestMeshIdx = mi;
          }
        }

        if (bestVertex < 0 || bestDist > 10) return; // too far from any vertex

        const hemi: "lh" | "rh" = bestMeshIdx === 0 ? "lh" : "rh";
        const hemiMap = hemi === "lh" ? atlas.lh : atlas.rh;
        const roi = hemiMap[bestVertex] || "";
        if (!roi) return;

        const info = atlas.roi_info[roi];

        // Get activation value from the overlay layer
        let activation = NaN;
        const mesh = nv.meshes[bestMeshIdx];
        if (mesh?.layers?.length > 0) {
          const layer = mesh.layers[0];
          const nVert = hemiMap.length;
          const frame = layer.frame4D ?? 0;
          const offset = frame * nVert + bestVertex;
          if (layer.values && offset < layer.values.length) {
            activation = layer.values[offset];
          }
        }

        cb({
          roi,
          fullName: info?.full_name ?? roi,
          category: info?.category ?? "other",
          hemi,
          activation,
          vertexIndex: bestVertex,
        });
      };

      // Wire single-click to trigger depth-pick (NiiVue only does this on double-click by default)
      const canvas = canvasRef.current;
      clickHandler = (e: MouseEvent) => {
        if (!nv.gl?.canvas) return;
        // Only act on genuine clicks (not after drag)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const pos = nv.getNoPaddingNoBorderCanvasRelativeMousePosition(e, nv.gl.canvas as any);
        if (!pos) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const dpr = (nv.uiData as any)?.dpr ?? window.devicePixelRatio ?? 1;
        const x = pos.x * dpr;
        const y = pos.y * dpr;
        if (nv.inRenderTile(x, y) >= 0) {
          nv.mousePos = [x, y];
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (nv.uiData as any).mouseDepthPicker = true;
          nv.drawScene();
          nv.drawScene(); // second call completes depth-pick + fires onLocationChange
        }
      };
      canvas.addEventListener("click", clickHandler);

      await loadGeometry(nv, meshType, jobId, isOpen, ver);
    })().catch(console.error);

    return () => {
      cancelled = true;
      if (canvasRef.current && clickHandler) {
        // eslint-disable-next-line react-hooks/exhaustive-deps
        canvasRef.current.removeEventListener("click", clickHandler);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  // ── Morph geometry when meshType or isOpen changes ─────────────────────
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv) return;

    const key = `${meshType}-${jobId ?? ""}-${isOpen}`;
    if (loadedGeoRef.current === key) return;

    isOpenRef.current = isOpen;
    meshTypeRef.current = meshType;

    const ver = ++versionRef.current;
    if (
      nv.meshes.length >= 2 &&
      nv.meshes[0].pts?.length > 0 &&
      nv.meshes[1].pts?.length > 0
    ) {
      morphGeometry(nv, meshType, isOpen, ver);
    } else {
      loadGeometry(nv, meshType, jobId, isOpen, ver).catch(console.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meshType, isOpen]);

  // ── Switch 4D frame when timestep or layersReady changes ──────────────
  useEffect(() => {
    if (layersReady) {
      setFrame(timestep);
    }
  }, [timestep, layersReady, setFrame]);

  // ── Re-frame when the panel is resized (canvas shape changes) ──────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === "undefined") return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ro = new ResizeObserver(() => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        scaleCache.clear();
        const nv = nvRef.current;
        if (nv?.scene && loadedGeoRef.current) {
          autoFit(nv, getFitTarget(meshTypeRef.current, isOpenRef.current));
        }
      }, 200);
    });
    ro.observe(canvas);
    return () => {
      if (timer) clearTimeout(timer);
      ro.disconnect();
    };
  }, []);

  // ── Snap back to the canonical camera on demand ────────────────────────
  useEffect(() => {
    if (resetSignal === undefined) return;
    const nv = nvRef.current;
    if (!nv?.scene) return;
    const targetCam = cameraForMode(isOpenRef.current);
    const targetRatio = getFitTarget(meshTypeRef.current, isOpenRef.current);
    const gl = nv.gl;
    const dims = gl ? `${gl.drawingBufferWidth}x${gl.drawingBufferHeight}` : "";
    const cacheKey = `${meshTypeRef.current}-${isOpenRef.current}-${dims}`;
    const targetScale = computeScaleForMesh(
      nv,
      nv.meshes.map((m: { pts: Float32Array }) => m.pts),
      targetCam,
      targetRatio,
      cacheKey,
    );
    animateCameraTo(nv, targetCam, targetScale);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetSignal]);

  /**
   * Own the keyboard for the brain view.
   *
   * NiiVue installs its own `keydown` listener directly on the canvas and its
   * arrow-key handling dereferences a loaded volume, so in a mesh-only scene it
   * throws a TypeError on every keypress. Intercepting in the capture phase on
   * the wrapper keeps the event from ever reaching that listener.
   */
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    function onKeyDown(e: KeyboardEvent) {
      const nv = nvRef.current;
      if (!nv?.scene) return;
      const step = e.shiftKey ? 15 : 5;
      let handled = true;
      switch (e.key) {
        case "ArrowLeft":
          nv.scene.renderAzimuth -= step;
          break;
        case "ArrowRight":
          nv.scene.renderAzimuth += step;
          break;
        case "ArrowUp":
          nv.scene.renderElevation = Math.min(
            90,
            nv.scene.renderElevation + step,
          );
          break;
        case "ArrowDown":
          nv.scene.renderElevation = Math.max(
            -90,
            nv.scene.renderElevation - step,
          );
          break;
        case "Home": {
          const targetCam = cameraForMode(isOpenRef.current);
          const targetRatio = getFitTarget(meshTypeRef.current, isOpenRef.current);
          const gl = nv.gl;
          const dims = gl ? `${gl.drawingBufferWidth}x${gl.drawingBufferHeight}` : "";
          const cacheKey = `${meshTypeRef.current}-${isOpenRef.current}-${dims}`;
          const targetScale = computeScaleForMesh(
            nv,
            nv.meshes.map((m: { pts: Float32Array }) => m.pts),
            targetCam,
            targetRatio,
            cacheKey,
          );
          animateCameraTo(nv, targetCam, targetScale);
          break;
        }
        default:
          handled = false;
      }
      // Block NiiVue's volume-oriented shortcuts either way.
      e.stopPropagation();
      if (handled) {
        e.preventDefault();
        nv.drawScene();
      }
    }
    host.addEventListener("keydown", onKeyDown, true);
    return () => host.removeEventListener("keydown", onKeyDown, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div ref={hostRef} className="relative h-full w-full">
      <canvas
        ref={canvasRef}
        tabIndex={0}
        role="img"
        aria-label="Interactive 3D brain surface. Drag to rotate, scroll to zoom, and click a region to read its name and activation. Arrow keys rotate; Home resets the view."
        className={`nl-brain-canvas ${ready ? "nl-brain-canvas--ready" : ""}`}
        style={{ outlineOffset: "-2px" }}
      />
      {!ready && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-canvas">
          <div className="flex flex-col items-center gap-3">
            <div
              aria-hidden
              className="h-8 w-8 rounded-full border-2 border-line border-t-accent animate-spin"
            />
            <p role="status" className="text-[11px] text-dim">
              Loading brain surface…
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
