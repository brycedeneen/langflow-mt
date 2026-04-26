import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ComponentsTab } from "./components-tab";
import { TagsTab } from "./tags-tab";

export default function MetadataPage() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">Component Management</h1>
      <Tabs defaultValue="components">
        <TabsList>
          <TabsTrigger value="components">Components</TabsTrigger>
          <TabsTrigger value="tags">Tags</TabsTrigger>
        </TabsList>
        <TabsContent value="components">
          <ComponentsTab />
        </TabsContent>
        <TabsContent value="tags">
          <TagsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
