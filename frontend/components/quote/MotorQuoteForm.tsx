"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

// Kept intentionally short for the initial quote - the platform should ask
// only what's needed to price the risk, not everything up front (spec §53:
// "insurance should feel simple", progressive disclosure).
export const motorQuoteSchema = z.object({
  registration_number: z.string().min(4, "Enter a valid registration number"),
  make: z.string().min(2, "Enter the vehicle make"),
  model: z.string().min(1, "Enter the vehicle model"),
  year: z.coerce.number().min(1990).max(new Date().getFullYear() + 1),
  value: z.coerce.number().positive("Enter the estimated vehicle value"),
  usage: z.enum(["private", "commercial", "psv"]),
  cover_type: z.enum(["comprehensive", "third_party", "third_party_fire_theft"]),
  owner_name: z.string().min(2, "Enter the owner's full name"),
  owner_phone: z.string().min(10, "Enter a valid phone number"),
});

export type MotorQuoteFormValues = z.infer<typeof motorQuoteSchema>;

export function MotorQuoteForm({ onSubmit, submitting }: { onSubmit: (v: MotorQuoteFormValues) => void; submitting: boolean }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MotorQuoteFormValues>({ resolver: zodResolver(motorQuoteSchema) });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="grid gap-5 sm:grid-cols-2">
      <Input label="Registration number" placeholder="KDA 123X" {...register("registration_number")} error={errors.registration_number?.message} />
      <Input label="Make" placeholder="Toyota" {...register("make")} error={errors.make?.message} />
      <Input label="Model" placeholder="Axio" {...register("model")} error={errors.model?.message} />
      <Input label="Year" type="number" {...register("year")} error={errors.year?.message} />
      <Input label="Estimated value (KES)" type="number" {...register("value")} error={errors.value?.message} />

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-ink">Usage</label>
        <select {...register("usage")} className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm">
          <option value="private">Private</option>
          <option value="commercial">Commercial</option>
          <option value="psv">PSV</option>
        </select>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-ink">Cover type</label>
        <select {...register("cover_type")} className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm">
          <option value="comprehensive">Comprehensive</option>
          <option value="third_party">Third Party</option>
          <option value="third_party_fire_theft">Third Party, Fire &amp; Theft</option>
        </select>
      </div>

      <Input label="Owner's full name" {...register("owner_name")} error={errors.owner_name?.message} />
      <Input label="Owner's phone" placeholder="07XX XXX XXX" {...register("owner_phone")} error={errors.owner_phone?.message} />

      <div className="sm:col-span-2">
        <Button type="submit" size="lg" disabled={submitting} className="w-full sm:w-auto">
          {submitting ? "Getting quotes…" : "Compare quotes"}
        </Button>
      </div>
    </form>
  );
}
