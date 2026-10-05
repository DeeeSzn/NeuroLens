/**
 * Ambient background for full-bleed routes: slow-drifting aurora blobs, a
 * radial vignette and fine film grain. Purely decorative and non-interactive,
 * it sits at z-0 behind app chrome. Motion is disabled under
 * prefers-reduced-motion via the .nl-aurora rule in globals.css.
 */
export default function Atmosphere({ ember = true }: { ember?: boolean }) {
  return (
    <div className="nl-atmosphere" aria-hidden>
      <div className="nl-aurora nl-aurora--violet" />
      <div className="nl-aurora nl-aurora--blue" />
      {ember && <div className="nl-aurora nl-aurora--ember" />}
      <div className="nl-vignette" />
      <div className="nl-grain" />
    </div>
  );
}
