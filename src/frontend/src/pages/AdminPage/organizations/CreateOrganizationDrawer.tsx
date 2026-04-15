import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateOrganization } from "@/controllers/API/queries/admin";
import useAlertStore from "@/stores/alertStore";
import IconComponent from "../../../components/common/genericIconComponent";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function CreateOrganizationDrawer() {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugManual, setSlugManual] = useState(false);
  const navigate = useNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutate: createOrg, isPending } = useCreateOrganization();

  function handleNameChange(value: string) {
    setName(value);
    if (!slugManual) {
      setSlug(toSlug(value));
    }
  }

  function handleSlugChange(value: string) {
    setSlugManual(true);
    setSlug(value);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !slug.trim()) return;

    createOrg(
      { name: name.trim(), slug: slug.trim() },
      {
        onSuccess: (org) => {
          navigate(`/admin/organizations/${org.id}`);
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to create organization",
            list: [
              error?.response?.data?.detail ?? "An unexpected error occurred.",
            ],
          });
        },
      },
    );
  }

  return (
    <div className="admin-page-panel flex h-full flex-col pb-8">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/admin/organizations")}
          >
            <IconComponent name="ChevronLeft" className="w-5" />
          </Button>
          <IconComponent name="Building2" className="w-6" />
          New Organization
        </span>
      </div>
      <span className="admin-page-description-text">
        Create a new platform organization.
      </span>

      <form
        onSubmit={handleSubmit}
        className="mt-6 flex max-w-md flex-col gap-4"
      >
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium" htmlFor="org-name">
            Name
          </label>
          <Input
            id="org-name"
            placeholder="My Organization"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            required
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium" htmlFor="org-slug">
            Slug
          </label>
          <Input
            id="org-slug"
            placeholder="my-organization"
            value={slug}
            onChange={(e) => handleSlugChange(e.target.value)}
            required
          />
          <span className="text-xs text-muted-foreground">
            URL-friendly identifier. Auto-derived from name; you can override.
          </span>
        </div>

        <div className="flex gap-3">
          <Button type="submit" variant="primary" disabled={isPending}>
            {isPending ? "Creating..." : "Create organization"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/admin/organizations")}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
