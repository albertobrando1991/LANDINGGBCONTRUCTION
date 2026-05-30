import { STAFF_PHOTOS } from "@/lib/assets";
import { initials } from "@/dashboard/leadMeta";

export function Avatar({ name, photo, size = 36, className = "" }) {
  const src = photo || STAFF_PHOTOS[name];
  const style = { width: size, height: size };
  if (src) {
    return <img src={src} alt={name || "avatar"} style={style} className={`rounded-full object-cover ${className}`} />;
  }
  return (
    <div style={style} className={`rounded-full bg-brand/20 text-brand flex items-center justify-center font-display font-bold ${className}`}>
      {initials(name)}
    </div>
  );
}
