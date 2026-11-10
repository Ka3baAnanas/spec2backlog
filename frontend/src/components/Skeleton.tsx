type SkeletonProps = {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  className?: string;
};

export function Skeleton({ width = "100%", height = 14, radius = 6, className = "" }: SkeletonProps) {
  return (
    <span
      className={`skeleton ${className}`.trim()}
      style={{ width, height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonLines({ lines = 3, gap = 10 }: { lines?: number; gap?: number }) {
  return (
    <div className="skeleton-stack" style={{ gap }} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? "62%" : "100%"} height={12} />
      ))}
    </div>
  );
}

export function ProjectCardSkeleton() {
  return (
    <div className="card card--pad" aria-hidden="true">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
        <Skeleton width={34} height={34} radius={9} />
        <Skeleton width={72} height={20} radius={999} />
      </div>
      <Skeleton width="76%" height={16} />
      <div style={{ marginTop: 8 }}>
        <Skeleton width="52%" height={12} />
      </div>
      <div style={{ marginTop: 26 }}>
        <Skeleton height={6} radius={999} />
      </div>
    </div>
  );
}
