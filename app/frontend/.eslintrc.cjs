module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
  },
  overrides: [
    {
      // Vendored shadcn/ui primitives and the context modules both ship a
      // component next to its variants/hook by design. Fast Refresh degrades
      // to a full reload for these files; that is the accepted trade-off
      // rather than splitting every upstream file we do not own.
      files: ['src/components/ui/**/*.tsx', 'src/contexts/**/*.tsx'],
      rules: { 'react-refresh/only-export-components': 'off' },
    },
  ],
}
