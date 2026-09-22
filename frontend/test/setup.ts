import { Glob } from "bun";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterEach, mock } from "bun:test";
import { createElement, type ComponentType } from "react";

const network = { fetch, Request, Response, Headers, AbortController, AbortSignal };
GlobalRegistrator.register({ url: "http://localhost" });
Object.assign(globalThis, network, { IS_REACT_ACT_ENVIRONMENT: true });

// CSS module class names are opaque to component behavior; Bun loads CSS as text.
for (const file of new Glob("src/**/*.module.css").scanSync({ cwd: `${import.meta.dir}/..`, absolute: true })) {
  mock.module(file, () => ({ default: new Proxy({}, { get: (_target, key) => String(key) }) }));
}

export const navigation = {
  pathname: "/",
  search: new URLSearchParams(),
  push: mock<(url: string) => void>(() => undefined),
  replace: mock<(url: string) => void>(() => undefined),
};
const router = { push: navigation.push, replace: navigation.replace };
mock.module("next/navigation", () => ({
  useRouter: () => router,
  usePathname: () => navigation.pathname,
  useSearchParams: () => navigation.search,
  notFound: () => { throw new Error("NEXT_NOT_FOUND"); },
}));
mock.module("next/server", () => ({ connection: async () => undefined }));
mock.module("next/font/google", () => ({ Vazirmatn: () => ({ variable: "font-test" }) }));
mock.module("next/link", () => ({
  default: ({ children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => createElement("a", props, children),
}));
mock.module("next/dynamic", () => ({
  default: (load: () => Promise<{ default: ComponentType }>) => {
    void load();
    return () => createElement("div", { "data-testid": "map-placeholder" });
  },
}));

export const avatarController = { play: mock(() => undefined), destroy: mock(() => undefined) };
export const createAvatar = mock(() => avatarController);
mock.module("@bible-strong/avatar-web", () => ({ createAvatar }));
export const markers: { click?: () => void }[] = [];
export const map = { setView: mock(() => undefined), fitBounds: mock(() => undefined), remove: mock(() => undefined) };
const layer = () => ({ addTo: mock(() => undefined) });
mock.module("leaflet", () => ({ default: {
  map: mock(() => map), tileLayer: mock(layer), circle: mock(layer),
  circleMarker: mock(() => {
    const handlers: { click?: () => void } = {};
    markers.push(handlers);
    const marker = { bindTooltip: () => marker, on: (_name: string, callback: () => void) => { handlers.click = callback; return marker; }, addTo: () => marker };
    return marker;
  }),
  latLngBounds: () => ({ pad: () => "bounds" }),
} }));

HTMLDialogElement.prototype.showModal = function () { this.open = true; };
HTMLDialogElement.prototype.close = function () { this.open = false; };
HTMLElement.prototype.scrollTo = () => undefined;

const { cleanup } = await import("@testing-library/react");
afterEach(() => {
  cleanup();
  localStorage.clear();
  navigation.pathname = "/";
  navigation.search = new URLSearchParams();
  navigation.push.mockClear();
  navigation.replace.mockClear();
  markers.length = 0;
});
