"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { PageHeader } from "@/components/common";
import { draftFrom, payloadFrom, PropertyForm } from "@/components/property-form";
import { api } from "@/lib/api";
import type { Property } from "@/lib/types";

export default function NewPropertyPage() {
  const router = useRouter();
  const qc = useQueryClient();
  return (
    <>
      <PageHeader
        title="Add a property"
        description={
          <>
            The asking price and your expected rent are enough to start. Have a shortlist already?{" "}
            <Link href="/data" className="font-medium text-wood underline underline-offset-2">
              Import a CSV
            </Link>
            .
          </>
        }
      />
      <PropertyForm
        initial={draftFrom()}
        submitLabel="Save property"
        onSubmit={async (d) => {
          const p = await api<Property>("/properties", { method: "POST", body: payloadFrom(d) });
          qc.invalidateQueries();
          toast.success("Property saved");
          router.push(`/properties/${p.id}`);
        }}
      />
    </>
  );
}
