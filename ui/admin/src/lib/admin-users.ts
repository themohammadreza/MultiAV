export function isCreateDisabled(username: string, password: string): boolean {
  return !username.trim() || !password;
}
