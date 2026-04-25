import { ComponentsTab } from "./components-tab";

export default function MetadataPage() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">Component Management</h1>
      <ComponentsTab />
    </div>
  );
}
