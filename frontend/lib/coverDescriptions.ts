// Plain-language explanations shown beside the motor cover types and the optional
// extra benefits, in the wording of the Somosure insurance products deck.

export const COVER_TYPE_DESCRIPTIONS: Record<string, string> = {
  third_party:
    "Covers injury or damage you cause to other people or their property. It does not cover damage to your own vehicle.",
  third_party_fire_theft:
    "Covers damage caused to third-party persons and their property, and also covers your own vehicle in case of fire, theft and accidental damage.",
  comprehensive:
    "Broad cover that includes damage to your own vehicle from accidents, theft, fire or natural disasters, and also covers damage caused to third-party persons and property.",
};

// Extension codes differ a little between insurers (e.g. excess_protector,
// excess_protector_own_damage), so these are matched by prefix.
const EXTENSION_DESCRIPTIONS: { prefix: string; text: string }[] = [
  {
    prefix: "excess_protector",
    text: "Helps cover the excess amount you would pay on eligible claims, subject to the benefit's limits and terms.",
  },
  {
    prefix: "pvt",
    text: "Cover for specified vehicle damage caused by covered political violence and terrorism events.",
  },
  {
    prefix: "political_violence",
    text: "Cover for specified vehicle damage caused by covered political violence and terrorism events.",
  },
  {
    prefix: "courtesy_car",
    text: "Temporary transport through a replacement vehicle while your insured car undergoes eligible repairs, subject to policy terms.",
  },
];

export function extensionDescription(code: string): string | null {
  return EXTENSION_DESCRIPTIONS.find((e) => code.startsWith(e.prefix))?.text ?? null;
}

// What a motor policy does not cover, as the deck lists it. Shown as a reminder on the quote form.
export const MOTOR_EXCLUSIONS = [
  "General wear and tear of the vehicle",
  "Mechanical or electrical breakdown",
  "Driving without a licence or under the influence of alcohol",
  "Using the vehicle for a purpose not covered under the policy",
];
