import { MantineColorsTuple, MantineThemeOverride, createTheme, rem } from '@mantine/core';

const primary: MantineColorsTuple = [
  '#eef5ff',
  '#d9e4ff',
  '#b0c7ff',
  '#82a7ff',
  '#5d8cff',
  '#447bff',
  '#3573ff',
  '#2b63e6',
  '#2557d0',
  '#1d47b9'
];

export const theme: MantineThemeOverride = createTheme({
  fontFamily: 'Inter, sans-serif',
  headings: { fontFamily: 'Inter, sans-serif' },
  colors: {
    primary
  },
  primaryColor: 'primary',
  defaultRadius: 'md',
  spacing: {
    xs: rem(8),
    sm: rem(12),
    md: rem(16),
    lg: rem(24),
    xl: rem(32)
  }
});
