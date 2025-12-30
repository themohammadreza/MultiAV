'use client';

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Modal,
  PasswordInput,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { IconPencil, IconTrash } from '@tabler/icons-react';
import { useMemo, useState } from 'react';
import { AdminUser } from '@/lib/api-types';
import { createAdminUser, deleteAdminUser, fetchAdminMe, listAdminUsers, updateAdminUser } from '@/lib/api-client';
import { isCreateDisabled } from '@/lib/admin-users';

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [createOpened, createModal] = useDisclosure(false);
  const [editOpened, editModal] = useDisclosure(false);
  const [deleteOpened, deleteModal] = useDisclosure(false);

  const [createUsername, setCreateUsername] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [createConfirmPassword, setCreateConfirmPassword] = useState('');
  const [createSuperadmin, setCreateSuperadmin] = useState(false);
  const [createTouched, setCreateTouched] = useState(false);

  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [editUsername, setEditUsername] = useState('');
  const [editPassword, setEditPassword] = useState('');
  const [editConfirmPassword, setEditConfirmPassword] = useState('');
  const [editCurrentPassword, setEditCurrentPassword] = useState('');
  const [editSuperadmin, setEditSuperadmin] = useState(false);
  const [editActive, setEditActive] = useState(true);
  const [editTouched, setEditTouched] = useState(false);

  const [deleteUser, setDeleteUser] = useState<AdminUser | null>(null);
  const [pendingUpdate, setPendingUpdate] = useState<{
    user: AdminUser;
    payload: {
      userId: string;
      username?: string;
      password?: string;
      is_superadmin?: boolean;
      is_active?: boolean;
    };
  } | null>(null);
  const [confirmDeactivateOpened, confirmDeactivateModal] = useDisclosure(false);

  const createDisabled = isCreateDisabled(createUsername, createPassword, createConfirmPassword);

  const adminMe = useQuery({
    queryKey: ['admin-me'],
    queryFn: fetchAdminMe,
    retry: false
  });
  const isSuperadmin = Boolean(adminMe.data?.is_superadmin);
  const currentAdminId = adminMe.data?.id;

  const usersQuery = useQuery({
    queryKey: ['admin-users'],
    queryFn: listAdminUsers,
    enabled: isSuperadmin
  });

  const users = usersQuery.data ?? [];
  const sortedUsers = useMemo(
    () => [...users].sort((a, b) => a.username.localeCompare(b.username)),
    [users]
  );
  const activeSuperadminCount = useMemo(
    () => users.filter((user) => user.is_superadmin && user.is_active).length,
    [users]
  );

  const createMutation = useMutation({
    mutationFn: () =>
      createAdminUser({
        username: createUsername.trim(),
        password: createPassword,
        is_superadmin: createSuperadmin
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      notifications.show({
        title: 'Admin created',
        message: `${data.username} is ready.`,
        color: 'green'
      });
      setCreateUsername('');
      setCreatePassword('');
      setCreateConfirmPassword('');
      setCreateSuperadmin(false);
      setCreateTouched(false);
      createModal.close();
    },
    onError: (error) => {
      notifications.show({ title: 'Create failed', message: error.message, color: 'red' });
    }
  });

  const updateMutation = useMutation({
    mutationFn: (payload: {
      userId: string;
      username?: string;
      password?: string;
      current_password?: string;
      is_superadmin?: boolean;
      is_active?: boolean;
    }) =>
      updateAdminUser(payload.userId, {
        username: payload.username,
        password: payload.password,
        current_password: payload.current_password,
        is_superadmin: payload.is_superadmin,
        is_active: payload.is_active
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      notifications.show({
        title: 'Admin updated',
        message: `${data.username} was updated.`,
        color: 'green'
      });
      editModal.close();
    },
    onError: (error) => {
      notifications.show({ title: 'Update failed', message: error.message, color: 'red' });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (userId: string) => deleteAdminUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      notifications.show({
        title: 'Admin removed',
        message: 'The admin account has been deleted.',
        color: 'orange'
      });
      deleteModal.close();
    },
    onError: (error) => {
      notifications.show({ title: 'Delete failed', message: error.message, color: 'red' });
    }
  });

  if (adminMe.isLoading) {
    return (
      <Stack gap="lg">
        <Title order={2}>Admin Users</Title>
        <Card withBorder>
          <Text size="sm" c="dimmed">
            Loading admin profile…
          </Text>
        </Card>
      </Stack>
    );
  }

  if (adminMe.isError) {
    return (
      <Stack gap="lg">
        <Title order={2}>Admin Users</Title>
        <Card withBorder>
          <Text size="sm" c="red">
            Unable to confirm admin permissions.
          </Text>
        </Card>
      </Stack>
    );
  }

  if (!isSuperadmin) {
    return (
      <Stack gap="lg">
        <Title order={2}>Admin Users</Title>
        <Card withBorder>
          <Stack gap="xs">
            <Text fw={600}>Superadmin access required</Text>
            <Text size="sm" c="dimmed">
              You do not have permission to manage admin accounts.
            </Text>
          </Stack>
        </Card>
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Admin Users</Title>
        <Button onClick={createModal.open}>Add admin</Button>
      </Group>

      <Modal
        opened={createOpened}
        onClose={() => {
          createModal.close();
          setCreateTouched(false);
        }}
        title="Add admin user"
        centered
      >
        <form
          autoComplete="off"
          onSubmit={(event) => {
            event.preventDefault();
            setCreateTouched(true);
            if (isCreateDisabled(createUsername, createPassword, createConfirmPassword)) {
              return;
            }
            createMutation.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="Username"
              name="username"
              autoComplete="new-username"
              placeholder="admin"
              value={createUsername}
              onChange={(event) => setCreateUsername(event.currentTarget.value)}
              error={createTouched && !createUsername.trim()}
            />
            <PasswordInput
              label="Password"
              name="password"
              autoComplete="new-password"
              placeholder="Create a password"
              value={createPassword}
              onChange={(event) => setCreatePassword(event.currentTarget.value)}
              error={createTouched && !createPassword}
            />
            <PasswordInput
              label="Confirm password"
              name="confirm-password"
              autoComplete="new-password"
              placeholder="Re-enter the password"
              value={createConfirmPassword}
              onChange={(event) => setCreateConfirmPassword(event.currentTarget.value)}
              error={createTouched && (!createConfirmPassword || createPassword !== createConfirmPassword)}
            />
            <Switch
              label="Grant superadmin access"
              checked={createSuperadmin}
              onChange={(event) => setCreateSuperadmin(event.currentTarget.checked)}
            />
            {createTouched && createDisabled && (
              <Text size="xs" c="red">
                * Enter a username and matching passwords to enable Create.
              </Text>
            )}
            <Group justify="flex-end">
              <Button variant="default" type="button" onClick={createModal.close}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createDisabled}
              >
                Create
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Modal
        opened={editOpened}
        onClose={() => {
          editModal.close();
          setEditTouched(false);
        }}
        title="Update admin user"
        centered
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setEditTouched(true);
            if (!editingUser) return;
            const trimmedUsername = editUsername.trim();
            const requiresPasswordConfirm = Boolean(editPassword);
            const isSelfEdit = editingUser.id === currentAdminId;
            if (
              requiresPasswordConfirm &&
              (!editConfirmPassword || editConfirmPassword !== editPassword)
            ) {
              return;
            }
            if (requiresPasswordConfirm && isSelfEdit && !editCurrentPassword) {
              return;
            }
            const payload: {
              userId: string;
              username?: string;
              password?: string;
              current_password?: string;
              is_superadmin?: boolean;
              is_active?: boolean;
            } = { userId: editingUser.id };
            if (trimmedUsername && trimmedUsername !== editingUser.username) {
              payload.username = trimmedUsername;
            }
            if (editPassword) {
              payload.password = editPassword;
              if (isSelfEdit) {
                payload.current_password = editCurrentPassword;
              }
            }
            if (editSuperadmin !== editingUser.is_superadmin) {
              payload.is_superadmin = editSuperadmin;
            }
            if (editActive !== editingUser.is_active) {
              payload.is_active = editActive;
            }
            if (
              !payload.username &&
              !payload.password &&
              payload.is_superadmin === undefined &&
              payload.is_active === undefined
            ) {
              notifications.show({
                title: 'No changes',
                message: 'Update at least one field before saving.',
                color: 'yellow'
              });
              return;
            }
            if (
              payload.is_active === false &&
              editingUser.is_superadmin &&
              editingUser.id !== currentAdminId
            ) {
              setPendingUpdate({ user: editingUser, payload });
              confirmDeactivateModal.open();
              editModal.close();
              return;
            }
            updateMutation.mutate(payload);
          }}
        >
          <Stack>
            <TextInput
              label="Username"
              value={editUsername}
              onChange={(event) => setEditUsername(event.currentTarget.value)}
            />
            <PasswordInput
              label="New password"
              placeholder="Enter a new password"
              value={editPassword}
              onChange={(event) => setEditPassword(event.currentTarget.value)}
              error={editTouched && !editConfirmPassword && Boolean(editPassword)}
            />
            <PasswordInput
              label="Confirm new password"
              placeholder="Re-enter the new password"
              value={editConfirmPassword}
              onChange={(event) => setEditConfirmPassword(event.currentTarget.value)}
              error={editTouched && Boolean(editPassword) && editConfirmPassword !== editPassword}
            />
            {editingUser?.id === currentAdminId && (
              <PasswordInput
                label="Current password"
                placeholder="Confirm your current password"
                value={editCurrentPassword}
                onChange={(event) => setEditCurrentPassword(event.currentTarget.value)}
                error={editTouched && Boolean(editPassword) && !editCurrentPassword}
              />
            )}
            <Switch
              label="Superadmin access"
              checked={editSuperadmin}
              onChange={(event) => setEditSuperadmin(event.currentTarget.checked)}
            />
            <Switch
              label="Active"
              checked={editActive}
              disabled={Boolean(
                (editingUser?.is_superadmin && editingUser.is_active && activeSuperadminCount <= 1) ||
                  editingUser?.id === currentAdminId
              )}
              onChange={(event) => setEditActive(event.currentTarget.checked)}
            />
            {editingUser?.id === currentAdminId && (
              <Text size="xs" c="dimmed">
                You cannot deactivate your own account.
              </Text>
            )}
            {editTouched && editPassword && !editConfirmPassword && (
              <Text size="xs" c="red">
                * Confirm the new password to continue.
              </Text>
            )}
            {editTouched && editPassword && editConfirmPassword && editConfirmPassword !== editPassword && (
              <Text size="xs" c="red">
                * Passwords do not match.
              </Text>
            )}
            {editTouched && editPassword && editingUser?.id === currentAdminId && !editCurrentPassword && (
              <Text size="xs" c="red">
                * Enter your current password to confirm the change.
              </Text>
            )}
            <Group justify="flex-end">
              <Button variant="default" type="button" onClick={editModal.close}>
                Cancel
              </Button>
              <Button type="submit">Save changes</Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Modal opened={deleteOpened} onClose={deleteModal.close} title="Delete admin user?" centered>
        <Stack>
          <Text>
            This will permanently remove <strong>{deleteUser?.username}</strong>.
          </Text>
          {deleteUser?.is_superadmin && (
            <Text size="sm" c="red">
              User {deleteUser.username} is a superadmin. Are you sure?
            </Text>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={deleteModal.close}>
              Cancel
            </Button>
            <Button
              color="red"
              onClick={() => {
                if (!deleteUser) return;
                deleteMutation.mutate(deleteUser.id);
              }}
            >
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={confirmDeactivateOpened}
        onClose={() => {
          setPendingUpdate(null);
          confirmDeactivateModal.close();
        }}
        title="Deactivate superadmin?"
        centered
      >
        <Stack>
          <Text>
            User <strong>{pendingUpdate?.user.username}</strong> is a superadmin. Are you sure you want to deactivate
            this account?
          </Text>
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                setPendingUpdate(null);
                confirmDeactivateModal.close();
              }}
            >
              Cancel
            </Button>
            <Button
              color="orange"
              onClick={() => {
                if (!pendingUpdate) return;
                updateMutation.mutate(pendingUpdate.payload);
                setPendingUpdate(null);
                confirmDeactivateModal.close();
              }}
            >
              Deactivate
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Card withBorder>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Username</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Last login</Table.Th>
              <Table.Th>Updated</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sortedUsers.map((user) => (
              <Table.Tr key={user.id}>
                <Table.Td>
                  <Text fw={600}>{user.username}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge color={user.is_superadmin ? 'blue' : 'gray'} variant="light">
                    {user.is_superadmin ? 'Superadmin' : 'Admin'}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Badge color={user.is_active ? 'green' : 'red'} variant="light">
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    <Tooltip
                      label={
                        user.id === currentAdminId
                          ? 'You cannot deactivate your own account.'
                          : 'At least one active superadmin is required.'
                      }
                      disabled={
                        !(user.is_superadmin && user.is_active && activeSuperadminCount <= 1) &&
                        user.id !== currentAdminId
                      }
                    >
                      <Switch
                        size="sm"
                        checked={user.is_active}
                        disabled={
                          (user.is_superadmin && user.is_active && activeSuperadminCount <= 1) ||
                          user.id === currentAdminId
                        }
                        onChange={(event) => {
                          const nextActive = event.currentTarget.checked;
                          if (!nextActive && user.is_superadmin && user.id !== currentAdminId) {
                            setPendingUpdate({
                              user,
                              payload: { userId: user.id, is_active: nextActive }
                            });
                            confirmDeactivateModal.open();
                            return;
                          }
                          updateMutation.mutate({ userId: user.id, is_active: nextActive });
                        }}
                        aria-label={user.is_active ? 'Deactivate admin' : 'Activate admin'}
                      />
                    </Tooltip>
                  </Group>
                </Table.Td>
                <Table.Td>{formatDate(user.last_login_at)}</Table.Td>
                <Table.Td>{formatDate(user.updated_at)}</Table.Td>
                <Table.Td>
                  <Group gap="xs" justify="flex-end">
                    <ActionIcon
                      variant="default"
                      aria-label="Edit admin"
                    onClick={() => {
                      setEditingUser(user);
                      setEditUsername(user.username);
                      setEditPassword('');
                      setEditConfirmPassword('');
                      setEditCurrentPassword('');
                      setEditSuperadmin(user.is_superadmin);
                      setEditActive(user.is_active);
                      setEditTouched(false);
                      editModal.open();
                    }}
                  >
                      <IconPencil size={16} />
                    </ActionIcon>
                    <ActionIcon
                      variant="default"
                      color="red"
                      aria-label="Delete admin"
                      onClick={() => {
                        setDeleteUser(user);
                        deleteModal.open();
                      }}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        {sortedUsers.length === 0 && (
          <Text size="sm" c="dimmed" ta="center" mt="sm">
            No admin users found.
          </Text>
        )}
      </Card>
    </Stack>
  );
}
