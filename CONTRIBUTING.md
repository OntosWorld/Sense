# Contributing to Sense

Thank you for your interest in contributing to Sense!

## Development Setup

1. Clone the repository
2. Install dependencies: `npm install`
3. Run the build: `npm run build`
4. Run tests: `npm test`
5. Run type checking: `npm run typecheck`
6. Run linting: `npm run lint`

## Code Style

We use Prettier for formatting and ESLint for linting. Configure your editor to use the project's `.prettierrc` settings.

Run `npm run format` to format all code.

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

Format: `<type>(<scope>): <description>`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`
Scopes: `core`, `schema`, `state`, `rules`, `events`, `peaq`, `ros2`, `market`, `docs`, `ci`, `build`, `security`

## Testing

All new features must include tests. Run tests with:

```bash
npm test
```

For watch mode during development:

```bash
npm run test:watch
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests
5. Ensure all checks pass: `npm run validate`
6. Submit a pull request

## Quality Gates

Every pull request must pass:

- TypeScript type checking
- ESLint linting
- Prettier formatting check
- Unit tests
- Package build

## License

By contributing to Sense, you agree that your contributions will be licensed under the Apache-2.0 license.
