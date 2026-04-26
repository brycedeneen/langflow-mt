import * as Form from "@radix-ui/react-form";
import { Eye, EyeOff } from "lucide-react";
import { useContext, useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import RolePicker from "@/components/common/rolePicker";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { CONTROL_NEW_USER } from "../../constants/constants";
import type { MembershipRole } from "@/constants/roles";
import { AuthContext } from "../../contexts/authContext";
import { useGetOrganizations } from "@/controllers/API/queries/admin";
import type {
  inputHandlerEventType,
  UserInputType,
  UserManagementType,
} from "../../types/components";
import BaseModal from "../baseModal";

export default function UserManagementModal({
  title,
  titleHeader,
  cancelText,
  confirmationText,
  children,
  icon,
  data,
  index,
  onConfirm,
  asChild,
}: UserManagementType) {
  const [pwdVisible, setPwdVisible] = useState(false);
  const [confirmPwdVisible, setConfirmPwdVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState(data?.password ?? "");
  const [username, setUserName] = useState(data?.username ?? "");
  const [confirmPassword, setConfirmPassword] = useState(data?.password ?? "");
  const [isActive, setIsActive] = useState(data?.is_active ?? false);
  const [isSuperUser, setIsSuperUser] = useState(data?.is_superuser ?? false);
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(
    data?.is_platform_admin ?? false,
  );
  const [inputState, setInputState] = useState<UserInputType>(CONTROL_NEW_USER);
  const [organizationId, setOrganizationId] = useState("");
  const [orgQuery, setOrgQuery] = useState("");
  const [role, setRole] = useState<MembershipRole>("member");
  const { userData } = useContext(AuthContext);

  const isCreateMode = !data;
  const needsOrg = isCreateMode && !isSuperUser && !isPlatformAdmin;

  const { data: orgsData, isLoading: isOrgsLoading } = useGetOrganizations(
    { q: orgQuery || undefined, limit: 20 },
    {
      enabled: isCreateMode && userData?.is_platform_admin === true,
    },
  );
  const orgItems = (orgsData?.items ?? []).filter((o) => !o.is_personal);
  const hasAnyOrgs = orgItems.length > 0 || orgQuery !== "";

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  useEffect(() => {
    if (isSuperUser || isPlatformAdmin) {
      setOrganizationId("");
      setOrgQuery("");
      setRole("member");
      setInputState((prev) => ({
        ...prev,
        organization_id: "",
        role: "member",
      }));
    }
  }, [isSuperUser, isPlatformAdmin]);

  useEffect(() => {
    if (open) {
      if (!data) {
        resetForm();
      } else {
        setUserName(data.username);
        setIsActive(data.is_active);
        setIsSuperUser(data.is_superuser);
        setIsPlatformAdmin(data.is_platform_admin ?? false);

        handleInput({ target: { name: "username", value: data.username } });
        handleInput({ target: { name: "is_active", value: data.is_active } });
        handleInput({
          target: { name: "is_superuser", value: data.is_superuser },
        });
        handleInput({
          target: { name: "is_platform_admin", value: data.is_platform_admin ?? false },
        });
      }
    }
  }, [open]);

  function resetForm() {
    setInputState(CONTROL_NEW_USER);
    setPassword("");
    setUserName("");
    setConfirmPassword("");
    setIsActive(false);
    setIsSuperUser(false);
    setIsPlatformAdmin(false);
    setOrganizationId("");
    setOrgQuery("");
    setRole("member");
  }

  return (
    <BaseModal size="medium-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger asChild={asChild}>{children}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader}>
        <span className="pr-2">{title}</span>
        <IconComponent
          name={icon}
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root
          onSubmit={(event) => {
            if (password !== confirmPassword) {
              event.preventDefault();
              return;
            }
            resetForm();
            onConfirm(1, inputState);
            setOpen(false);
            event.preventDefault();
          }}
        >
          <div className="grid gap-5">
            <Form.Field name="username">
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                }}
              >
                <Form.Label className="data-[invalid]:label-invalid">
                  Username{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
              </div>
              <Form.Control asChild>
                <input
                  onChange={({ target: { value } }) => {
                    handleInput({ target: { name: "username", value } });
                    setUserName(value);
                  }}
                  value={username}
                  className="primary-input"
                  required
                  placeholder="Username"
                />
              </Form.Control>
              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your username
              </Form.Message>
            </Form.Field>

            <div className="flex flex-row">
              <div className="mr-3 basis-1/2">
                <Form.Field
                  name="password"
                  serverInvalid={password != confirmPassword}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                    }}
                  >
                    <Form.Label className="data-[invalid]:label-invalid flex">
                      Password{" "}
                      <span className="ml-1 mr-1 font-medium text-destructive">
                        *
                      </span>
                      {pwdVisible && (
                        <Eye
                          onClick={() => setPwdVisible(!pwdVisible)}
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                      {!pwdVisible && (
                        <EyeOff
                          onClick={() => setPwdVisible(!pwdVisible)}
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                    </Form.Label>
                  </div>
                  <Form.Control asChild>
                    <input
                      onChange={({ target: { value } }) => {
                        handleInput({ target: { name: "password", value } });
                        setPassword(value);
                      }}
                      value={password}
                      className="primary-input"
                      required={data ? false : true}
                      type={pwdVisible ? "text" : "password"}
                    />
                  </Form.Control>

                  <Form.Message className="field-invalid" match="valueMissing">
                    Please enter a password
                  </Form.Message>

                  {password != confirmPassword && (
                    <Form.Message className="field-invalid">
                      Passwords do not match
                    </Form.Message>
                  )}
                </Form.Field>
              </div>

              <div className="basis-1/2">
                <Form.Field
                  name="confirmpassword"
                  serverInvalid={password != confirmPassword}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                    }}
                  >
                    <Form.Label className="data-[invalid]:label-invalid flex">
                      Confirm password{" "}
                      <span className="ml-1 mr-1 font-medium text-destructive">
                        *
                      </span>
                      {confirmPwdVisible && (
                        <Eye
                          onClick={() =>
                            setConfirmPwdVisible(!confirmPwdVisible)
                          }
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                      {!confirmPwdVisible && (
                        <EyeOff
                          onClick={() =>
                            setConfirmPwdVisible(!confirmPwdVisible)
                          }
                          className="h-5 cursor-pointer"
                          strokeWidth={1.5}
                        />
                      )}
                    </Form.Label>
                  </div>
                  <Form.Control asChild>
                    <input
                      onChange={(input) => {
                        setConfirmPassword(input.target.value);
                      }}
                      value={confirmPassword}
                      className="primary-input"
                      required={data ? false : true}
                      type={confirmPwdVisible ? "text" : "password"}
                    />
                  </Form.Control>
                  <Form.Message className="field-invalid" match="valueMissing">
                    Please confirm your password
                  </Form.Message>
                </Form.Field>
              </div>
            </div>
            <div className="flex gap-8">
              <Form.Field name="is_active">
                <div>
                  <Form.Label className="data-[invalid]:label-invalid mr-3">
                    Active
                  </Form.Label>
                  {data?.id === userData?.id ? (
                    <Tooltip delayDuration={500}>
                      <TooltipTrigger asChild>
                        <span className="inline-block cursor-not-allowed">
                          <Checkbox
                            value={isActive}
                            checked={isActive}
                            id="is_active"
                            className="relative top-0.5 pointer-events-none opacity-50"
                            disabled
                          />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent
                        className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                        avoidCollisions={false}
                        sticky="always"
                      >
                        You cannot deactivate your own account
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <Form.Control asChild>
                      <Checkbox
                        value={isActive}
                        checked={isActive}
                        id="is_active"
                        className="relative top-0.5"
                        onCheckedChange={(value) => {
                          handleInput({ target: { name: "is_active", value } });
                          setIsActive(value);
                        }}
                      />
                    </Form.Control>
                  )}
                </div>
              </Form.Field>
              {userData?.is_superuser && (
                <Form.Field name="is_superuser">
                  <div>
                    <Form.Label className="data-[invalid]:label-invalid mr-3">
                      Superuser
                    </Form.Label>
                    <Form.Control asChild>
                      <Checkbox
                        checked={isSuperUser}
                        value={isSuperUser}
                        id="is_superuser"
                        className="relative top-0.5"
                        onCheckedChange={(value) => {
                          handleInput({
                            target: { name: "is_superuser", value },
                          });
                          setIsSuperUser(value);
                        }}
                      />
                    </Form.Control>
                  </div>
                </Form.Field>
              )}
              {userData?.is_platform_admin && (
                <Form.Field name="is_platform_admin">
                  <div>
                    <Form.Label className="data-[invalid]:label-invalid mr-3">
                      Platform Admin
                    </Form.Label>
                    <Form.Control asChild>
                      <Checkbox
                        checked={isPlatformAdmin}
                        value={isPlatformAdmin}
                        id="is_platform_admin"
                        className="relative top-0.5"
                        onCheckedChange={(value) => {
                          handleInput({
                            target: { name: "is_platform_admin", value },
                          });
                          setIsPlatformAdmin(value);
                        }}
                        data-testid="new-user-is-platform-admin"
                      />
                    </Form.Control>
                  </div>
                </Form.Field>
              )}
            </div>

            {needsOrg && (
              <div className="flex flex-col gap-3">
                <Form.Field name="organization_id">
                  <Form.Label className="data-[invalid]:label-invalid">
                    Organization <span className="font-medium text-destructive">*</span>
                  </Form.Label>
                  {!hasAnyOrgs && !isOrgsLoading ? (
                    <div
                      className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
                      data-testid="new-user-no-orgs-message"
                    >
                      No organizations exist. Create one in Admin → Organizations first.
                    </div>
                  ) : (
                    <>
                      <Input
                        placeholder="Search organizations..."
                        value={orgQuery}
                        onChange={(e) => setOrgQuery(e.target.value)}
                        data-testid="new-user-org-search"
                      />
                      <ul
                        className="mt-2 max-h-48 overflow-auto rounded-md border"
                        data-testid="new-user-org-list"
                      >
                        {orgItems.map((o) => (
                          <li
                            key={o.id}
                            className={`cursor-pointer px-3 py-2 hover:bg-muted ${
                              organizationId === o.id ? "bg-muted" : ""
                            }`}
                            onClick={() => {
                              setOrganizationId(o.id);
                              handleInput({
                                target: { name: "organization_id", value: o.id },
                              });
                            }}
                            data-testid={`new-user-org-option-${o.id}`}
                          >
                            {o.name}
                          </li>
                        ))}
                        {orgItems.length === 0 && !isOrgsLoading && (
                          <li className="px-3 py-2 text-muted-foreground">No matches.</li>
                        )}
                      </ul>
                    </>
                  )}
                </Form.Field>

                <Form.Field name="role">
                  <Form.Label className="data-[invalid]:label-invalid mr-3">
                    Role <span className="font-medium text-destructive">*</span>
                  </Form.Label>
                  <RolePicker
                    caller="platform_admin"
                    current={role}
                    onSelect={(next) => {
                      setRole(next);
                      handleInput({ target: { name: "role", value: next } });
                    }}
                  />
                </Form.Field>
              </div>
            )}
          </div>

          <div className="float-right">
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
              }}
              className="mr-3"
            >
              {cancelText}
            </Button>

            <Form.Submit asChild>
              <Button
                className="mt-8"
                disabled={
                  needsOrg &&
                  (!organizationId || (!hasAnyOrgs && !isOrgsLoading))
                }
                data-testid="new-user-save"
              >
                {confirmationText}
              </Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
