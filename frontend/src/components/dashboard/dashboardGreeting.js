/**
 * Time-of-day greeting themes for the dashboard banner.
 * Pure helpers — no React, no DOM — so they stay testable.
 */
import bannerMorning from '../../assets/dashboard/banner-morning.jpg';
import bannerAfternoon from '../../assets/dashboard/banner-afternoon.jpg';
import bannerEvening from '../../assets/dashboard/banner-evening.jpg';
import bannerNight from '../../assets/dashboard/banner-night.jpg';

export const GREETING_SLOTS = ['morning', 'afternoon', 'evening', 'night'];

/**
 * Morning 05–11, Afternoon 12–16, Evening 17–20, Night 21–04 (user's local clock).
 * @param {Date} [date]
 * @returns {'morning'|'afternoon'|'evening'|'night'}
 */
export function resolveGreetingSlot(date = new Date()) {
  const hour = date instanceof Date && !Number.isNaN(date.getTime()) ? date.getHours() : 9;
  if (hour >= 5 && hour <= 11) return 'morning';
  if (hour >= 12 && hour <= 16) return 'afternoon';
  if (hour >= 17 && hour <= 20) return 'evening';
  return 'night';
}

/**
 * Photographic themes matching the product reference banners.
 * `tone` drives text / chip contrast: light for morning/afternoon, dark for evening/night.
 */
export const GREETING_THEMES = {
  morning: {
    slot: 'morning',
    label: 'Good Morning',
    message: "Let's make today a successful day.",
    quote: 'New Opportunities Begin Every Morning',
    sidePhrase: 'A Brighter Tomorrow',
    brandLine: 'PAY · GROW · TOGETHER',
    image: bannerMorning,
    tone: 'light',
  },
  afternoon: {
    slot: 'afternoon',
    label: 'Good Afternoon',
    message: "Keep going! You're doing great.",
    quote: 'Consistent Effort Creates Great Results',
    sidePhrase: 'Same People Bigger Possibilities',
    brandLine: 'PAY · GROW · TOGETHER',
    image: bannerAfternoon,
    tone: 'light',
  },
  evening: {
    slot: 'evening',
    label: 'Good Evening',
    message: 'Progress happens one transaction at a time.',
    quote: 'Small Payments Create Bigger Tomorrows',
    sidePhrase: 'Progress Looks Good on You',
    brandLine: 'PAY · GROW · TOGETHER',
    image: bannerEvening,
    tone: 'dark',
  },
  night: {
    slot: 'night',
    label: 'Good Night',
    message: 'Rest well. A bigger tomorrow awaits.',
    quote: 'End Today with Confidence',
    sidePhrase: 'Good Ideas Never Sleep',
    brandLine: 'PAY · GROW · TOGETHER',
    image: bannerNight,
    tone: 'dark',
  },
};

/** @param {Date} [date] */
export function greetingThemeFor(date = new Date()) {
  return GREETING_THEMES[resolveGreetingSlot(date)];
}

/** Milliseconds until the next hour boundary — used to re-check the slot cheaply. */
export function msUntilNextHour(date = new Date()) {
  const next = new Date(date.getTime());
  next.setMinutes(0, 0, 0);
  next.setHours(next.getHours() + 1);
  return Math.max(30000, next.getTime() - date.getTime());
}
