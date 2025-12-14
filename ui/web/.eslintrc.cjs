module.exports = {
  root: true,
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module'
  },
  extends: ['next/core-web-vitals', 'prettier'],
  rules: {
    'react/jsx-key': ['error', { checkFragmentShorthand: true }]
  }
};
