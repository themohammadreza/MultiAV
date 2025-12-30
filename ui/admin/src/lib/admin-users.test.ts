import { describe, expect, it } from 'vitest';
import { isCreateDisabled } from './admin-users';

describe('isCreateDisabled', () => {
  it('returns true when username is empty', () => {
    expect(isCreateDisabled('', 'secret', 'secret')).toBe(true);
  });

  it('returns true when username is whitespace', () => {
    expect(isCreateDisabled('   ', 'secret', 'secret')).toBe(true);
  });

  it('returns true when password is empty', () => {
    expect(isCreateDisabled('admin', '', '')).toBe(true);
  });

  it('returns true when confirm password is empty', () => {
    expect(isCreateDisabled('admin', 'secret', '')).toBe(true);
  });

  it('returns true when passwords do not match', () => {
    expect(isCreateDisabled('admin', 'secret', 'mismatch')).toBe(true);
  });

  it('returns false when both fields are provided', () => {
    expect(isCreateDisabled('admin', 'secret', 'secret')).toBe(false);
  });
});
