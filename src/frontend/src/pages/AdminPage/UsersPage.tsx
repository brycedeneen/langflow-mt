import { cloneDeep } from "lodash";
import { useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PaginatorComponent from "@/components/common/paginatorComponent";
import { useAddMember } from "@/controllers/API/queries/admin";
import {
  useAddUser,
  useDeleteUsers,
  useGetUsers,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import CustomLoader from "@/customization/components/custom-loader";
import IconComponent, {
  ForwardedIconComponent,
} from "../../components/common/genericIconComponent";
import ShadTooltip from "../../components/common/shadTooltipComponent";
import { Button } from "../../components/ui/button";
import { CheckBoxDiv } from "../../components/ui/checkbox";
import { Input } from "../../components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import {
  USER_ADD_ERROR_ALERT,
  USER_ADD_SUCCESS_ALERT,
  USER_DEL_ERROR_ALERT,
  USER_DEL_SUCCESS_ALERT,
  USER_EDIT_ERROR_ALERT,
  USER_EDIT_SUCCESS_ALERT,
} from "../../constants/alerts_constants";
import {
  PAGINATION_PAGE,
  PAGINATION_ROWS_COUNT,
  PAGINATION_SIZE,
} from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import ConfirmationModal from "../../modals/confirmationModal";
import UserManagementModal from "../../modals/userManagementModal";
import useAlertStore from "../../stores/alertStore";
import type { Users } from "../../types/api";
import type { UserInputType } from "../../types/components";

export default function UsersPage() {
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState("");

  const [size, setPageSize] = useState(PAGINATION_SIZE);
  const [index, setPageIndex] = useState(PAGINATION_PAGE);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData } = useContext(AuthContext);
  const [totalRowsCount, setTotalRowsCount] = useState(0);

  const { mutate: mutateDeleteUser } = useDeleteUsers();
  const { mutate: mutateUpdateUser } = useUpdateUser();
  const { mutate: mutateAddUser } = useAddUser();
  const { mutate: mutateAddMember } = useAddMember();

  const userList = useRef([]);

  useEffect(() => {
    setTimeout(() => {
      getUsers();
    }, 500);
  }, []);

  const [filterUserList, setFilterUserList] = useState(userList.current);

  const { mutate: mutateGetUsers, isPending, isIdle } = useGetUsers({});

  function getUsers() {
    mutateGetUsers(
      {
        skip: size * (index - 1),
        limit: size,
      },
      {
        onSuccess: (users) => {
          setTotalRowsCount(users["total_count"]);
          userList.current = users["users"];
          setFilterUserList(users["users"]);
        },
        onError: () => {},
      },
    );
  }

  function handleChangePagination(pageIndex: number, pageSize: number) {
    setPageSize(pageSize);
    setPageIndex(pageIndex);

    mutateGetUsers(
      {
        skip: pageSize * (pageIndex - 1),
        limit: pageSize,
      },
      {
        onSuccess: (users) => {
          setTotalRowsCount(users["total_count"]);
          userList.current = users["users"];
          setFilterUserList(users["users"]);
        },
      },
    );
  }

  function resetFilter() {
    setPageIndex(PAGINATION_PAGE);
    setPageSize(PAGINATION_SIZE);
    getUsers();
  }

  function handleFilterUsers(input: string) {
    setInputValue(input);

    if (input === "") {
      setFilterUserList(userList.current);
    } else {
      const filteredList = userList.current.filter((user: Users) =>
        user.username.toLowerCase().includes(input.toLowerCase()),
      );
      setFilterUserList(filteredList);
    }
  }

  function handleDeleteUser(user) {
    mutateDeleteUser(
      { user_id: user.id },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_DEL_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_DEL_ERROR_ALERT,
            list: [error["response"]["data"]["detail"]],
          });
        },
      },
    );
  }

  function handleEditUser(userId, user) {
    const { username, password, is_active, is_superuser, is_platform_admin } =
      user;
    const editableFields = {
      username,
      password,
      is_active,
      is_superuser,
      is_platform_admin,
    };
    mutateUpdateUser(
      { user_id: userId, user: editableFields },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_EDIT_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_EDIT_ERROR_ALERT,
            list: [error["response"]["data"]["detail"]],
          });
        },
      },
    );
  }

  function handleDisableUser(check, userId, user) {
    const userEdit = cloneDeep(user);
    userEdit.is_active = !check;

    mutateUpdateUser(
      { user_id: userId, user: userEdit },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_EDIT_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_EDIT_ERROR_ALERT,
            list: [error["response"]["data"]["detail"]],
          });
        },
      },
    );
  }

  function handleSuperUserEdit(check, userId, user) {
    const userEdit = cloneDeep(user);
    userEdit.is_superuser = !check;

    mutateUpdateUser(
      { user_id: userId, user: userEdit },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_EDIT_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_EDIT_ERROR_ALERT,
            list: [error["response"]["data"]["detail"]],
          });
        },
      },
    );
  }

  function handlePlatformAdminEdit(check, userId, user) {
    const userEdit = cloneDeep(user);
    userEdit.is_platform_admin = !check;

    mutateUpdateUser(
      { user_id: userId, user: userEdit },
      {
        onSuccess: () => {
          resetFilter();
          setSuccessData({
            title: USER_EDIT_SUCCESS_ALERT,
          });
        },
        onError: (error) => {
          setErrorData({
            title: USER_EDIT_ERROR_ALERT,
            list: [error["response"]["data"]["detail"]],
          });
        },
      },
    );
  }

  function handleNewUser(user: UserInputType) {
    mutateAddUser(user, {
      onSuccess: (res) => {
        const newUserId = res["id"];
        mutateUpdateUser(
          {
            user_id: newUserId,
            user: {
              is_active: user.is_active,
              is_superuser: user.is_superuser,
              is_platform_admin: user.is_platform_admin,
            },
          },
          {
            onSuccess: () => {
              if (user.organization_id) {
                mutateAddMember(
                  {
                    orgId: user.organization_id,
                    user_id: newUserId,
                    role: user.role ?? "member",
                  },
                  {
                    onSuccess: () => {
                      resetFilter();
                      setSuccessData({ title: USER_ADD_SUCCESS_ALERT });
                    },
                    onError: (error) => {
                      resetFilter();
                      setErrorData({
                        title: "User created, but could not be added to organization. Add them from the organization page.",
                        list: [error["response"]?.["data"]?.["detail"] ?? String(error)],
                      });
                    },
                  },
                );
              } else {
                resetFilter();
                setSuccessData({ title: USER_ADD_SUCCESS_ALERT });
              }
            },
            onError: (error) => {
              resetFilter();
              setErrorData({
                title: "User created, but role flags could not be applied. Please edit the user to set roles.",
                list: [error["response"]?.["data"]?.["detail"] ?? String(error)],
              });
            },
          },
        );
      },
      onError: (error) => {
        setErrorData({
          title: USER_ADD_ERROR_ALERT,
          list: [error["response"]["data"]["detail"]],
        });
      },
    });
  }

  return (
    <>
      {userData && (
        <div className="flex h-full w-full flex-col gap-6">
          <div className="flex w-full items-start justify-between gap-6">
            <div className="flex flex-col">
              <h2
                className="flex items-center text-lg font-semibold tracking-tight"
                data-testid="settings_menu_header"
              >
                User Admin
                <ForwardedIconComponent
                  name="Users"
                  className="ml-2 h-5 w-5 text-primary"
                />
              </h2>
              <p className="text-sm text-muted-foreground">
                Manage user accounts for this Amplify instance.
              </p>
            </div>
            <div className="shrink-0">
              <UserManagementModal
                title="New User"
                titleHeader={"Add a new user"}
                cancelText="Cancel"
                confirmationText="Save"
                icon={"UserPlus2"}
                onConfirm={(index, user) => {
                  handleNewUser(user);
                }}
                asChild
              >
                <Button variant="primary">New User</Button>
              </UserManagementModal>
            </div>
          </div>
          <div className="flex w-full justify-between">
            <div className="flex w-96 items-center gap-4">
              <Input
                placeholder="Search Username"
                value={inputValue}
                onChange={(e) => handleFilterUsers(e.target.value)}
              />
              {inputValue.length > 0 ? (
                <div
                  className="cursor-pointer"
                  onClick={() => {
                    setInputValue("");
                    setFilterUserList(userList.current);
                  }}
                >
                  <IconComponent name="X" className="w-6 text-foreground" />
                </div>
              ) : (
                <div>
                  <IconComponent
                    name="Search"
                    className="w-6 text-foreground"
                  />
                </div>
              )}
            </div>
          </div>
          {isPending || isIdle ? (
            <div className="flex h-full w-full items-center justify-center">
              <CustomLoader remSize={12} />
            </div>
          ) : userList.current.length === 0 && !isIdle ? (
            <>
              <div className="m-4 flex items-center justify-between text-sm">
                No users registered.
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col">
              <div
                className={
                  "my-4 flex-1 overflow-x-hidden overflow-y-scroll rounded-md border bg-background custom-scroll" +
                  (isPending ? " border-0" : "")
                }
              >
                <Table className={"table-fixed outline-1"}>
                  <TableHeader
                    className={
                      isPending ? "hidden" : "table-fixed bg-muted outline-1"
                    }
                  >
                    <TableRow>
                      <TableHead className="h-10">Id</TableHead>
                      <TableHead className="h-10">Username</TableHead>
                      <TableHead className="h-10">Active</TableHead>
                      <TableHead className="h-10">Superuser</TableHead>
                      <TableHead className="h-10">Platform Admin</TableHead>
                      <TableHead className="h-10">Created At</TableHead>
                      <TableHead className="h-10">Updated At</TableHead>
                      <TableHead className="h-10 w-[100px] text-right"></TableHead>
                    </TableRow>
                  </TableHeader>
                  {!isPending && (
                    <TableBody className="border-b">
                      {filterUserList.map((user: UserInputType, index) => (
                        <TableRow key={index}>
                          <TableCell className="truncate py-2 font-medium">
                            <ShadTooltip content={user.id}>
                              <span className="cursor-default">{user.id}</span>
                            </ShadTooltip>
                          </TableCell>
                          <TableCell className="truncate py-2">
                            <ShadTooltip content={user.username}>
                              <button
                                className="cursor-pointer text-left hover:underline"
                                onClick={() =>
                                  navigate(`/settings/users/${user.id}`)
                                }
                              >
                                {user.username}
                              </button>
                            </ShadTooltip>
                          </TableCell>
                          <TableCell className="relative left-1 truncate py-2 text-align-last-left">
                            {user.id === userData?.id ? (
                              <ShadTooltip content="You cannot deactivate your own account">
                                <div className="flex w-fit cursor-not-allowed opacity-50">
                                  <CheckBoxDiv checked={user.is_active} />
                                </div>
                              </ShadTooltip>
                            ) : (
                              <ConfirmationModal
                                size="x-small"
                                title="Edit"
                                titleHeader={`${user.username}`}
                                modalContentTitle="Attention!"
                                cancelText="Cancel"
                                confirmationText="Confirm"
                                icon={"UserCog2"}
                                data={user}
                                index={index}
                                onConfirm={(index, user) => {
                                  handleDisableUser(
                                    user.is_active,
                                    user.id,
                                    user,
                                  );
                                }}
                              >
                                <ConfirmationModal.Content>
                                  <span>
                                    Are you completely confident about the
                                    changes you are making to this user?
                                  </span>
                                </ConfirmationModal.Content>
                                <ConfirmationModal.Trigger>
                                  <div className="flex w-fit">
                                    <CheckBoxDiv checked={user.is_active} />
                                  </div>
                                </ConfirmationModal.Trigger>
                              </ConfirmationModal>
                            )}
                          </TableCell>
                          <TableCell className="relative left-1 truncate py-2 text-align-last-left">
                            <ConfirmationModal
                              size="x-small"
                              title="Edit"
                              titleHeader={`${user.username}`}
                              modalContentTitle="Attention!"
                              cancelText="Cancel"
                              confirmationText="Confirm"
                              icon={"UserCog2"}
                              data={user}
                              index={index}
                              onConfirm={(index, user) => {
                                handleSuperUserEdit(
                                  user.is_superuser,
                                  user.id,
                                  user,
                                );
                              }}
                            >
                              <ConfirmationModal.Content>
                                <span>
                                  Are you completely confident about the changes
                                  you are making to this user?
                                </span>
                              </ConfirmationModal.Content>
                              <ConfirmationModal.Trigger>
                                <div className="flex w-fit">
                                  <CheckBoxDiv checked={user.is_superuser} />
                                </div>
                              </ConfirmationModal.Trigger>
                            </ConfirmationModal>
                          </TableCell>
                          <TableCell className="relative left-1 truncate py-2 text-align-last-left">
                            <ConfirmationModal
                              size="x-small"
                              title="Edit"
                              titleHeader={`${user.username}`}
                              modalContentTitle="Attention!"
                              cancelText="Cancel"
                              confirmationText="Confirm"
                              icon={"UserCog2"}
                              data={user}
                              index={index}
                              onConfirm={(index, user) => {
                                handlePlatformAdminEdit(
                                  user.is_platform_admin,
                                  user.id,
                                  user,
                                );
                              }}
                            >
                              <ConfirmationModal.Content>
                                <span>
                                  Platform admins can manage organizations and
                                  memberships for this Amplify instance. Continue?
                                </span>
                              </ConfirmationModal.Content>
                              <ConfirmationModal.Trigger>
                                <div
                                  className="flex w-fit"
                                  data-testid={`platform-admin-cell-${user.username}`}
                                >
                                  <CheckBoxDiv
                                    checked={!!user.is_platform_admin}
                                  />
                                </div>
                              </ConfirmationModal.Trigger>
                            </ConfirmationModal>
                          </TableCell>
                          <TableCell className="truncate py-2">
                            {
                              new Date(user.create_at!)
                                .toISOString()
                                .split("T")[0]
                            }
                          </TableCell>
                          <TableCell className="truncate py-2">
                            {
                              new Date(user.updated_at!)
                                .toISOString()
                                .split("T")[0]
                            }
                          </TableCell>
                          <TableCell className="flex w-[100px] py-2 text-right">
                            <div className="flex">
                              <UserManagementModal
                                title="Edit"
                                titleHeader={`${user.id}`}
                                cancelText="Cancel"
                                confirmationText="Save"
                                icon={"UserPlus2"}
                                data={user}
                                index={index}
                                onConfirm={(index, editUser) => {
                                  handleEditUser(user.id, editUser);
                                }}
                              >
                                <ShadTooltip content="Edit" side="top">
                                  <IconComponent
                                    name="Pencil"
                                    className="h-4 w-4 cursor-pointer"
                                  />
                                </ShadTooltip>
                              </UserManagementModal>

                              <ConfirmationModal
                                size="x-small"
                                title="Delete"
                                titleHeader="Delete User"
                                modalContentTitle="Attention!"
                                cancelText="Cancel"
                                confirmationText="Delete"
                                icon={"UserMinus2"}
                                data={user}
                                index={index}
                                onConfirm={(index, user) => {
                                  handleDeleteUser(user);
                                }}
                              >
                                <ConfirmationModal.Content>
                                  <span>
                                    Are you sure you want to delete this user?
                                    This action cannot be undone.
                                  </span>
                                </ConfirmationModal.Content>
                                <ConfirmationModal.Trigger>
                                  <IconComponent
                                    name="Trash2"
                                    className="ml-2 h-4 w-4 cursor-pointer"
                                  />
                                </ConfirmationModal.Trigger>
                              </ConfirmationModal>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  )}
                </Table>
              </div>

              <div className="mt-auto">
                <PaginatorComponent
                  pageIndex={index}
                  pageSize={size}
                  totalRowsCount={totalRowsCount}
                  paginate={handleChangePagination}
                  rowsCount={PAGINATION_ROWS_COUNT}
                ></PaginatorComponent>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
