export function isCreateDisabled(username: string, password: string, confirmPassword: string): boolean {
  if (!username.trim() || !password || !confirmPassword) {
    return true;
  }
  return password !== confirmPassword;
}
