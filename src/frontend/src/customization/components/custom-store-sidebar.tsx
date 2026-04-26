import { Key, Store } from "lucide-react";

export const CustomStoreSidebar = (
  hasApiKey: boolean = false,
  hasStore: boolean = false,
) => {
  const items: Array<{ title: string; href: string; icon: JSX.Element }> = [];

  if (hasApiKey) {
    items.push({
      title: "Amplify API Keys",
      href: "/settings/api-keys",
      icon: (
        <Key
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  if (hasStore) {
    items.push({
      title: "Langflow Store",
      href: "/settings/store",
      icon: (
        <Store
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  return items;
};
