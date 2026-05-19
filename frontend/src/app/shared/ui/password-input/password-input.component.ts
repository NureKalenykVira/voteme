import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DoCheck,
  Input,
  inject,
  signal,
} from '@angular/core';
import { NgIf } from '@angular/common';
import { ControlValueAccessor, NgControl } from '@angular/forms';

@Component({
  selector: 'ui-password-input',
  standalone: true,
  imports: [NgIf],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './password-input.component.html',
  styleUrl: './password-input.component.scss',
})
export class PasswordInputComponent implements ControlValueAccessor, DoCheck {
  @Input() label = '';
  @Input() id = '';
  @Input() autocomplete = '';
  @Input() crossFieldErrorKey?: string;

  _value = '';
  readonly showPassword = signal(false);
  private readonly cdr = inject(ChangeDetectorRef);
  readonly ngControl = inject(NgControl, { self: true, optional: true });

  private _lastTouched = false;
  private _lastInvalid = false;
  private _lastParentInvalid = false;

  constructor() {
    if (this.ngControl) {
      this.ngControl.valueAccessor = this;
    }
  }

  ngDoCheck(): void {
    const c = this.ngControl?.control;
    if (!c) return;
    const touched = c.touched;
    const invalid = c.invalid;
    const parentInvalid = !!c.parent?.invalid;
    if (
      touched !== this._lastTouched ||
      invalid !== this._lastInvalid ||
      parentInvalid !== this._lastParentInvalid
    ) {
      this._lastTouched = touched;
      this._lastInvalid = invalid;
      this._lastParentInvalid = parentInvalid;
      this.cdr.markForCheck();
    }
  }

  get hasError(): boolean {
    const c = this.ngControl?.control;
    if (!c?.touched) return false;
    return c.invalid || !!(this.crossFieldErrorKey && c.parent?.errors?.[this.crossFieldErrorKey]);
  }

  get errorMessage(): string {
    const c = this.ngControl?.control;
    if (!c?.touched) return '';
    const e = c.errors;
    if (e?.['required']) return 'This field is required';
    if (e?.['minlength']) return `Minimum ${e['minlength'].requiredLength} characters`;
    if (e?.['noLetter']) return 'Must contain at least one letter';
    if (this.crossFieldErrorKey && c.parent?.errors?.[this.crossFieldErrorKey])
      return "Passwords don't match";
    return '';
  }

  onChange: (v: string) => void = () => {};
  onTouched: () => void = () => {};

  writeValue(v: string): void {
    this._value = v ?? '';
    this.cdr.markForCheck();
  }

  registerOnChange(fn: (v: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  onInput(event: Event): void {
    this._value = (event.target as HTMLInputElement).value;
    this.onChange(this._value);
  }
}
