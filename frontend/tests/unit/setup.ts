import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

// @testing-library/react's auto-cleanup only self-registers when Vitest's
// `globals: true` is set (it isn't — see vitest.config.ts); without this,
// each render() leaks into the next test's DOM within the same file.
afterEach(cleanup);
