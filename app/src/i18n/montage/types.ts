import type { montageUz } from "./uz";

/** Montaj lug'atlari aynan shu kalitlarga ega bo'lishi shart. */
export type MontageMessages = { readonly [K in keyof typeof montageUz]: string };
