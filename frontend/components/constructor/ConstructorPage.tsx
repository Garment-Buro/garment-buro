"use client";

import { useState } from "react";
import { ConstructorWorkspace } from "@/components/constructor/ConstructorWorkspace";
import { useConstructorPageController } from "@/hooks/constructor/useConstructorPageController";
import type { ConstructorPageProps } from "@/lib/constructor/types";
import { useCustomerAccount } from "@/hooks/catalog/customerSession";
import { nextConstructorLifetime } from "@/lib/constructor/lifetime";

function ConstructorEditor(props: ConstructorPageProps) {
  const controller = useConstructorPageController(props);
  return <ConstructorWorkspace controller={controller} />;
}

export default function ConstructorPage(props: ConstructorPageProps = {}) {
  const account = useCustomerAccount();
  const [lifetime, setLifetime] = useState(() => ({
    account: account.key,
    revision: 0,
  }));
  const current = nextConstructorLifetime(lifetime, account.key);
  if (current !== lifetime) setLifetime(current);
  const key = props.projectId
    ? `project:${props.projectId}:${account.key ?? "guest"}`
    : `new:${props.productId ?? ""}:${props.draftId ?? ""}:${props.editCartItemId ?? ""}:${current.revision}`;
  return <ConstructorEditor key={key} {...props} />;
}
