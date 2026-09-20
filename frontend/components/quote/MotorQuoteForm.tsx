"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

// Kept intentionally short for the initial quote - the platform should ask
// only what's needed to price the risk, not everything up front (spec §53:
// "insurance should feel simple", progressive disclosure). `vehicle_class`
// is an optional override for providers priced through the rate-card
// engine (AMACO, Pioneer Insurance Kenya - see docs/RATE_CARDS.md on the
// backend): left blank, the backend infers a sensible class from `usage`
// (and `psv_type` for PSV); set it explicitly to reach a specific class
// like a school bus or a motorcycle that a plain usage value can't express.
export const motorQuoteSchema = z.object({
  registration_number: z.string().min(4, "Enter a valid registration number"),
  make: z.string().min(2, "Enter the vehicle make"),
  model: z.string().min(1, "Enter the vehicle model"),
  year: z.coerce.number().min(1990).max(new Date().getFullYear() + 1),
  value: z.coerce.number().positive("Enter the estimated vehicle value"),
  usage: z.enum(["private", "commercial", "psv"]),
  cover_type: z.enum(["comprehensive", "third_party", "third_party_fire_theft"]),
  vehicle_class: z.string().optional(),
  psv_type: z.enum(["taxi_yellow", "taxi_chauffeur", "taxi_online", "tour_van", "matatu", "bus", "tuktuk"]).optional(),
  tonnage: z.coerce.number().positive().optional(),
  seating_capacity: z.coerce.number().int().positive().optional(),
  owner_name: z.string().min(2, "Enter the owner's full name"),
  owner_phone: z.string().min(10, "Enter a valid phone number"),
});

export type MotorQuoteFormValues = z.infer<typeof motorQuoteSchema>;

// Canonical rate-card class codes a customer can pick directly instead of
// relying on the usage-based default - see docs/RATE_CARDS.md.
const VEHICLE_CLASS_OPTIONS = [
  { value: "", label: "Match automatically from usage above" },
  { value: "motor_private", label: "Private car" },
  { value: "motor_private_fleet_individual", label: "Private fleet (3+ vehicles, individual)" },
  { value: "motor_private_fleet_corporate", label: "Private fleet (5+ vehicles, corporate)" },
  { value: "motor_commercial_own_goods", label: "Commercial - own goods only" },
  { value: "motor_commercial_general_cartage", label: "Commercial - general cartage / hire & reward" },
  { value: "motor_commercial_prime_mover_tanker", label: "Prime mover / tanker" },
  { value: "merchant_commercial_hybrid", label: "Merchant commercial hybrid" },
  { value: "motor_commercial_asset", label: "Commercial asset (plant & machinery)" },
  { value: "institution_corporate_bus", label: "Institution/corporate bus or passenger van" },
  { value: "school_bus", label: "School bus" },
  { value: "ambulance_fire", label: "Ambulance or fire engine" },
  { value: "motorcycle_own_use", label: "Motorcycle (corporate-owned, own use)" },
  { value: "tractor_special_type", label: "Tractor / grader / caterpillar / bulldozer" },
  { value: "driving_school", label: "Driving school vehicle" },
  { value: "motor_trade", label: "Motor trade (road risk)" },
];

export function MotorQuoteForm({ onSubmit, submitting }: { onSubmit: (v: MotorQuoteFormValues) => void; submitting: boolean }) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<MotorQuoteFormValues>({ resolver: zodResolver(motorQuoteSchema), defaultValues: { usage: "private" } });

  const usage = useWatch({ control, name: "usage" });

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

      {usage === "psv" && (
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-ink">PSV type</label>
          <select {...register("psv_type")} className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm">
            <option value="taxi_online">Taxi - online (Uber-type)</option>
            <option value="taxi_yellow">Taxi - yellow line</option>
            <option value="taxi_chauffeur">Taxi - chauffeur driven</option>
            <option value="tour_van">Tour van</option>
            <option value="matatu">Matatu</option>
            <option value="bus">Bus</option>
            <option value="tuktuk">Tuktuk</option>
          </select>
        </div>
      )}

      {usage === "psv" && (
        <Input
          label="Seating capacity (excl. driver)"
          type="number"
          placeholder="14"
          {...register("seating_capacity")}
          error={errors.seating_capacity?.message}
        />
      )}

      {usage === "commercial" && (
        <Input
          label="Tonnage (for goods-carrying vehicles)"
          type="number"
          step="0.1"
          placeholder="7"
          {...register("tonnage")}
          error={errors.tonnage?.message}
        />
      )}

      <div className="flex flex-col gap-1.5 sm:col-span-2">
        <label className="text-sm font-medium text-ink">Specific vehicle class (optional)</label>
        <select {...register("vehicle_class")} className="rounded-control border border-neutral-border bg-white px-4 py-2.5 text-sm">
          {VEHICLE_CLASS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-neutral-500">
          Only needed for a category that doesn&apos;t fit Private/Commercial/PSV neatly - e.g. a school bus or a
          driving-school car. Leave on &quot;match automatically&quot; otherwise.
        </p>
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
