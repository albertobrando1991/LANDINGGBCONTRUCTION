import { brand } from "@/brand/identity";

const SIZE = {
  sm: "h-9 w-9 md:h-10 md:w-10",
  md: "h-11 w-11",
  lg: "h-14 w-14",
};

export default function BrandMark({
  size = "md",
  showName = false,
  name = brand.sidebarName || brand.name,
  className = "",
  nameClassName = "font-display font-bold uppercase text-ink",
}) {
  const box = SIZE[size] || SIZE.md;
  const useLogo = brand.mark === "logo" && brand.logoSrc;

  return (
    <div className={`flex items-center gap-3 ${className}`.trim()}>
      <div className={`${box} shrink-0 rounded-full p-[2px] accent-metallic animate-gradient-shift`}>
        {useLogo ? (
          <img
            src={brand.logoSrc}
            alt=""
            className="h-full w-full rounded-full bg-bg object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center rounded-full bg-bg font-display font-bold text-sm text-ink">
            {brand.initials}
          </div>
        )}
      </div>
      {showName ? <span className={nameClassName}>{name}</span> : null}
    </div>
  );
}
