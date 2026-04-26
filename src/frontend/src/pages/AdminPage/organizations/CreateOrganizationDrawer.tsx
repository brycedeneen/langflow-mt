import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateOrganization } from "@/controllers/API/queries/admin";
import useAlertStore from "@/stores/alertStore";
import { ChevronLeft } from "lucide-react";
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
          navigate(`/settings/organizations/${org.id}`);
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
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center gap-2 text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/settings/organizations")}
            >
              <ChevronLeft className="w-5" />
            </Button>
            New Organization
          </h2>
          <p className="pl-11 text-sm text-muted-foreground">
            Create a new platform organization.
          </p>
        </div>
      </div>

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
            onClick={() => navigate("/settings/organizations")}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
