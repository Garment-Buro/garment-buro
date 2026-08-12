import type { SVGProps } from "react";

export type AppIconName =
    | "arrow-up"
    | "back"
    | "chevron-up"
    | "customer"
    | "delete"
    | "discount-lock"
    | "expand"
    | "info"
    | "map-pin"
    | "size-filter";

type AppIconProps = Omit<SVGProps<SVGSVGElement>, "children"> & {
    name: AppIconName;
    title?: string;
};

const ICON_VIEW_BOX: Record<AppIconName, string> = {
    "arrow-up": "0 0 8 7",
    back: "0 0 25 21",
    "chevron-up": "0 0 12 10",
    customer: "0 0 11 16",
    delete: "0 0 16 18",
    "discount-lock": "0 0 11 15",
    expand: "0 0 9 9",
    info: "0 0 15 15",
    "map-pin": "0 0 10 12",
    "size-filter": "0 0 16 11",
};

const IconPath = ({ name }: { name: AppIconName }) => {
    switch (name) {
        case "arrow-up":
            return <path d="M7.5 6.5 4 .5.5 6.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />;
        case "back":
            return (
                <>
                    <path d="M11.857 1 1 10.5 11.857 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M1 10.5h22.167" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </>
            );
        case "chevron-up":
            return <path d="M.5 9.5 6 .5l5.5 9" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />;
        case "customer":
            return (
                <>
                    <circle cx="5.5" cy="2.5" r="2" fill="none" stroke="currentColor" />
                    <path d="M.5 11c0-2.76 2.24-5 5-5s5 2.24 5 5" fill="none" stroke="currentColor" strokeLinejoin="round" />
                </>
            );
        case "delete":
            return <path d="M5.4 13.5 8 10.9l2.6 2.6 1.4-1.4-2.6-2.6L12 6.9l-1.4-1.4L8 8.1 5.4 5.5 4 6.9l2.6 2.6L4 12.1l1.4 1.4ZM3 18c-.55 0-1.02-.196-1.413-.588A1.926 1.926 0 0 1 1 16V3H0V1h5V0h6v1h5v2h-1v13c0 .55-.196 1.02-.588 1.412A1.926 1.926 0 0 1 13 18H3Zm10-15H3v13h10V3Z" fill="currentColor" />;
        case "discount-lock":
            return <path d="M1.375 15A1.36 1.36 0 0 1 0 13.571V6.43A1.36 1.36 0 0 1 1.375 5h.688V3.571C2.063 1.59 3.6 0 5.5 0s3.438 1.59 3.438 3.571V5h.687A1.36 1.36 0 0 1 11 6.429v7.142A1.36 1.36 0 0 1 9.625 15h-8.25Zm0-1.429h8.25V6.43h-8.25v7.142ZM5.5 11.43c.76 0 1.375-.64 1.375-1.429S6.26 8.571 5.5 8.571 4.125 9.211 4.125 10s.616 1.429 1.375 1.429ZM3.438 5h4.124V3.571c0-1.19-.923-2.142-2.062-2.142s-2.063.952-2.063 2.142V5Z" fill="currentColor" />;
        case "expand":
            return (
                <>
                    <path d="M6.1.5h2.4v2.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M.5 6.1v2.4h2.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
                </>
            );
        case "info":
            return (
                <>
                    <path d="M6.633 5.13v-.95H7.71v.95H6.633Zm0 4.87V5.724H7.71V10H6.633Z" fill="currentColor" />
                    <circle cx="7.166" cy="7.166" r="6.677" fill="none" stroke="currentColor" strokeWidth=".977" />
                </>
            );
        case "map-pin":
            return <path d="M5.883 5.648A1.17 1.17 0 0 0 6.25 4.8c0-.33-.122-.613-.367-.848A1.24 1.24 0 0 0 5 3.6c-.344 0-.638.118-.883.352A1.17 1.17 0 0 0 3.75 4.8c0 .33.122.613.367.848C4.362 5.883 4.656 6 5 6s.638-.117.883-.352ZM5 10.41c1.27-1.12 2.214-2.138 2.828-3.053.615-.915.922-1.727.922-2.437 0-1.09-.362-1.983-1.086-2.678C6.94 1.547 6.052 1.2 5 1.2s-1.94.347-2.664 1.042C1.612 2.937 1.25 3.83 1.25 4.92c0 .71.307 1.522.922 2.437C2.786 8.272 3.73 9.29 5 10.41ZM5 12C3.323 10.63 2.07 9.358 1.242 8.183.414 7.008 0 5.92 0 4.92c0-1.5.503-2.695 1.508-3.585C2.513.445 3.677 0 5 0s2.487.445 3.492 1.335C9.497 2.225 10 3.42 10 4.92c0 1-.414 2.088-1.242 3.263C7.93 9.358 6.677 10.63 5 12Z" fill="currentColor" />;
        case "size-filter":
            return (
                <>
                    <path d="M.5 2h15M.5 9h15" fill="none" stroke="currentColor" strokeLinecap="round" />
                    <circle cx="9.875" cy="2" r="1.375" fill="currentColor" stroke="currentColor" />
                    <circle cx="6.125" cy="9" r="1.375" fill="currentColor" stroke="currentColor" />
                </>
            );
    }
};

export function AppIcon({ name, title, color, ...props }: AppIconProps) {
    return (
        <svg
            {...props}
            viewBox={ICON_VIEW_BOX[name]}
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            color={color ?? "currentColor"}
            focusable="false"
            aria-hidden={title ? undefined : true}
            role={title ? "img" : undefined}
        >
            {title && <title>{title}</title>}
            <IconPath name={name} />
        </svg>
    );
}
