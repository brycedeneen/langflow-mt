import { Skeleton } from "../../ui/skeleton";

export const SkeletonCardComponent = (): JSX.Element => {
  return (
    <div className="flex h-48 flex-col gap-6 rounded-lg border bg-background p-4">
      <div className="flex items-center space-x-4">
        <Skeleton className="h-8 w-8 rounded-full" />
        <Skeleton className="h-4 w-[40%]" />
      </div>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-3 w-[90%]" />
        <Skeleton className="h-3 w-[80%]" />
      </div>
    </div>
  );
};
