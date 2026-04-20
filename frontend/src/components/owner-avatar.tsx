import { cn } from "@/lib/utils";
import type { Owner } from "@/lib/mock-data";

const PALETTE = [
  "bg-blue-500/15 text-blue-300 ring-blue-500/30",
  "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  "bg-violet-500/15 text-violet-300 ring-violet-500/30",
  "bg-rose-500/15 text-rose-300 ring-rose-500/30",
  "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30",
];

function pickPalette(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]!.toUpperCase())
    .join("");
}

type OwnerAvatarProps = {
  owner: Owner;
  size?: "sm" | "md";
  className?: string;
};

export function OwnerAvatar({ owner, size = "sm", className }: OwnerAvatarProps) {
  const sizeClasses = size === "md" ? "h-7 w-7 text-[11px]" : "h-6 w-6 text-[10px]";
  return (
    <div
      title={`${owner.name} · ${owner.role}`}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full font-medium ring-1 ring-inset",
        sizeClasses,
        pickPalette(owner.id),
        className,
      )}
    >
      {initialsFor(owner.name)}
    </div>
  );
}

type OwnerStackProps = {
  owners: Owner[];
  max?: number;
};

export function OwnerStack({ owners, max = 3 }: OwnerStackProps) {
  const shown = owners.slice(0, max);
  const overflow = owners.length - shown.length;
  return (
    <div className="flex items-center -space-x-1.5">
      {shown.map((o) => (
        <OwnerAvatar
          key={o.id}
          owner={o}
          className="ring-2 ring-card"
        />
      ))}
      {overflow > 0 ? (
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground ring-2 ring-card">
          +{overflow}
        </div>
      ) : null}
    </div>
  );
}
