export type ProfileTab = "my-collection" | "profile" | "unfinished";
export type ProfilePanelTab = "discounts" | "orders" | "support" | "settings";
export type BottomPanelState = "collapsed" | "normal" | "expanded";

export type ProfileOrder = {
    id: string;
    title: string;
    date: string;
    total: string;
    paid: boolean;
};
