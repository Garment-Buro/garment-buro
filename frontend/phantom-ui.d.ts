import type { PhantomUiAttributes } from "@aejkatappaja/phantom-ui";

declare module "react" {
    namespace JSX {
        interface IntrinsicElements {
            "phantom-ui": PhantomUiAttributes;
        }
    }
}
