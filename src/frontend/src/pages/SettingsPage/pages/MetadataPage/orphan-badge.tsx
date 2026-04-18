import ForwardedIconComponent from "@/components/common/genericIconComponent";

export function OrphanBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
      <ForwardedIconComponent name="AlertTriangle" className="w-3 h-3" />
      Orphan
    </span>
  );
}
