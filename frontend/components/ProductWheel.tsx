"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
    Car,
    HeartPulse,
    Umbrella,
    Home,
    Plane,
    Briefcase,
    UserCheck,
    Scale,
    HardHat,
    ChevronLeft,
    ChevronRight,
    type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface WheelItem {
    category: string;
    name: string;
    href: string;
    desc: string;
}

const ICONS: Record<string, LucideIcon> = {
    motor: Car,
    medical: HeartPulse,
    life: Umbrella,
    home: Home,
    travel: Plane,
    business: Briefcase,
    personal_accident: UserCheck,
    professional_indemnity: Scale,
    wiba: HardHat,
};

const AUTOPLAY_MS = 3200;

/**
 * A Ferris-wheel-style rotating showcase: items are arranged along an arc
 * and continuously cycle through the front position. Built with plain
 * trigonometry (no extra deps) so it degrades gracefully - every item is
 * still a real, focusable, keyboard-reachable control even before JS
 * computes its position.
 */
export function ProductWheel({ items, compact = false }: { items: WheelItem[]; compact?: boolean }) {
    const total = items.length;
    const [active, setActive] = useState(0);
    const [paused, setPaused] = useState(false);
    const [radius, setRadius] = useState(compact ? { x: 155, y: 34 } : { x: 260, y: 85 });
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const updateRadius = () => {
            const w = window.innerWidth;
            if (compact) {
                setRadius(w < 480 ? { x: 82, y: 26 } : { x: 155, y: 34 });
                return;
            }
            if (w < 480) setRadius({ x: 110, y: 44 });
            else if (w < 768) setRadius({ x: 175, y: 62 });
            else setRadius({ x: 260, y: 85 });
        };
        updateRadius();
        window.addEventListener("resize", updateRadius);
        return () => window.removeEventListener("resize", updateRadius);
    }, [compact]);

    useEffect(() => {
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (paused || prefersReducedMotion || total <= 1) return;
        const id = setInterval(() => setActive((a) => (a + 1) % total), AUTOPLAY_MS);
        return () => clearInterval(id);
    }, [paused, total]);

    const goTo = useCallback((i: number) => setActive(((i % total) + total) % total), [total]);

    function onKeyDown(e: React.KeyboardEvent) {
        if (e.key === "ArrowRight") goTo(active + 1);
        if (e.key === "ArrowLeft") goTo(active - 1);
    }

    const activeItem = items[active];

    return (
        <div
            ref={containerRef}
            className="w-full"
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
            onFocus={() => setPaused(true)}
            onBlur={() => setPaused(false)}
            onKeyDown={onKeyDown}
        >
            <div className={`relative mx-auto select-none overflow-x-clip ${compact ? "h-32 sm:h-36" : "h-44 sm:h-56 md:h-64"}`} aria-hidden={false}>
                {items.map((item, i) => {
                    let raw = i - active;
                    if (raw > total / 2) raw -= total;
                    if (raw < -total / 2) raw += total;
                    const visible = Math.abs(raw) <= (compact ? 3 : 4);
                    const angle = raw * (360 / total);
                    const rad = (angle * Math.PI) / 180;
                    const x = Math.sin(rad) * radius.x;
                    const y = (1 - Math.cos(rad)) * radius.y;
                    const scale = Math.max(1 - Math.abs(raw) * 0.13, 0.5);
                    const opacity = visible ? Math.max(1 - Math.abs(raw) * 0.2, 0.15) : 0;
                    const Icon = ICONS[item.category] ?? Car;
                    const isActive = raw === 0;

                    return (
                        <button
                            key={item.href}
                            type="button"
                            aria-label={`Show ${item.name}`}
                            aria-current={isActive}
                            tabIndex={visible ? 0 : -1}
                            onClick={() => goTo(i)}
                            style={{
                                transform: `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${scale})`,
                                opacity,
                                zIndex: 100 - Math.round(Math.abs(raw) * 10),
                                pointerEvents: visible ? "auto" : "none",
                            }}
                            className={`absolute left-1/2 flex flex-col items-center gap-2 transition-transform duration-500 ease-out focus:outline-none ${compact ? "top-2" : "top-4"}`}
                        >
                            <span
                                className={`flex items-center justify-center rounded-full border shadow-card transition-colors ${compact ? "h-9 w-9" : "h-14 w-14 sm:h-16 sm:w-16"
                                    } ${isActive ? "border-brand-deep bg-brand text-ink" : "border-neutral-border bg-white text-ink-soft"}`}
                            >
                                <Icon className={compact ? "h-4 w-4" : "h-6 w-6 sm:h-7 sm:w-7"} />
                            </span>
                            <span
                                className={`text-center font-medium ${isActive ? "text-ink" : "text-ink-soft"} ${compact ? "max-w-[4.5rem] text-[10px] leading-tight" : "max-w-[6rem] text-xs"
                                    }`}
                            >
                                {item.name}
                            </span>
                        </button>
                    );
                })}
            </div>

            <div className={`mx-auto flex items-center justify-center gap-3 ${compact ? "mt-3 max-w-xs" : "mt-6 max-w-md"}`}>
                <button
                    type="button"
                    aria-label="Previous product"
                    onClick={() => goTo(active - 1)}
                    className="rounded-full border border-neutral-border p-2 text-ink-soft transition-colors hover:border-brand-deep hover:text-ink"
                >
                    <ChevronLeft className="h-4 w-4" />
                </button>

                <AnimatePresence mode="wait">
                    <motion.div
                        key={activeItem.href}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.25 }}
                        className="flex flex-1 flex-col items-center gap-2 text-center"
                    >
                        <h3 className={compact ? "font-display text-sm font-bold" : "font-display text-lg font-bold"}>{activeItem.name}</h3>
                        {!compact && <p className="max-w-sm text-sm text-ink-soft">{activeItem.desc}</p>}
                        <Link href={activeItem.href} className="mt-1">
                            <Button className="w-full rounded-full">Get a quote</Button>
                        </Link>
                    </motion.div>
                </AnimatePresence>

                <button
                    type="button"
                    aria-label="Next product"
                    onClick={() => goTo(active + 1)}
                    className="rounded-full border border-neutral-border p-2 text-ink-soft transition-colors hover:border-brand-deep hover:text-ink"
                >
                    <ChevronRight className="h-4 w-4" />
                </button>
            </div>

            <div className={`flex justify-center gap-1.5 ${compact ? "mt-2" : "mt-4"}`}>
                {items.map((item, i) => (
                    <button
                        key={item.href}
                        type="button"
                        aria-label={`Go to ${item.name}`}
                        onClick={() => goTo(i)}
                        className={`h-1.5 rounded-full transition-all ${i === active ? "w-5 bg-brand-deep" : "w-1.5 bg-neutral-border"
                            }`}
                    />
                ))}
            </div>
        </div>
    );
}
