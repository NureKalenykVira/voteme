import { AbstractControl, ValidationErrors } from '@angular/forms';

const LETTER_RE = /[A-Za-z]/;

export function containsLetter(control: AbstractControl): ValidationErrors | null {
  const value = control.value;
  if (value === null || value === undefined || value === '') return null;
  return LETTER_RE.test(value) ? null : { noLetter: true };
}
