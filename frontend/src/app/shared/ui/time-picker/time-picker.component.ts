import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  HostListener,
  Input,
  forwardRef,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'ui-time-picker',
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TimePickerComponent),
      multi: true,
    },
  ],
  templateUrl: './time-picker.component.html',
  styleUrl: './time-picker.component.scss',
})
export class TimePickerComponent implements ControlValueAccessor {
  @Input() label = '';
  @Input() id = '';
  @Input() hasError = false;

  private readonly cdr = inject(ChangeDetectorRef);
  private readonly elRef = inject(ElementRef);

  readonly open = signal(false);

  hours = 0;
  minutes = 0;
  private _hasValue = false;
  private _disabled = false;

  inputFocused = false;
  inputValue = '';
  inputError = false;

  onChange: (v: string) => void = () => {};
  onTouched: () => void = () => {};

  // ── ControlValueAccessor ──────────────────────────────────────

  writeValue(v: string): void {
    if (v && /^\d{2}:\d{2}$/.test(v)) {
      const [h, m] = v.split(':').map(Number);
      this.hours = h;
      this.minutes = m;
      this._hasValue = true;
    } else {
      this.hours = 0;
      this.minutes = 0;
      this._hasValue = false;
    }
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  registerOnChange(fn: (v: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this._disabled = isDisabled;
    this.cdr.markForCheck();
  }

  get disabled(): boolean {
    return this._disabled;
  }

  // ── Display helpers ───────────────────────────────────────────

  get displayValue(): string {
    if (!this._hasValue) return '';
    return `${String(this.hours).padStart(2, '0')}:${String(this.minutes).padStart(2, '0')}`;
  }

  get hoursDisplay(): string {
    return String(this.hours).padStart(2, '0');
  }

  get minutesDisplay(): string {
    return String(this.minutes).padStart(2, '0');
  }

  // ── Input keyboard handling ───────────────────────────────────

  onInputFocus(): void {
    this.inputFocused = true;
    this.inputValue = this.displayValue;
    this.inputError = false;
    this.onTouched();
    this.cdr.markForCheck();
  }

  onInputBlur(): void {
    this.inputFocused = false;
    this.inputError = false;
    this.tryParseInput(this.inputValue);
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  onInputChange(value: string): void {
    const digits = value.replace(/\D/g, '');
    let formatted: string;
    if (digits.length <= 2) {
      formatted = digits;
    } else {
      formatted = `${digits.slice(0, 2)}:${digits.slice(2, 4)}`;
    }
    formatted = formatted.slice(0, 5);
    this.inputValue = formatted;

    if (digits.length === 4) {
      const h = Number(digits.slice(0, 2));
      const m = Number(digits.slice(2, 4));
      if (h >= 0 && h <= 23 && m >= 0 && m <= 59) {
        this.hours = h;
        this.minutes = m;
        this._hasValue = true;
        this.emitChange();
        this.inputError = false;
      } else {
        this.inputError = true;
      }
    } else {
      this.inputError = false;
    }
    this.cdr.markForCheck();
  }

  onInputEnter(): void {
    this.tryParseInput(this.inputValue);
    this.inputValue = this.displayValue;
    this.inputFocused = false;
    this.inputError = false;
    this.cdr.markForCheck();
  }

  private tryParseInput(value: string): void {
    const parsed = this.parseTime(value);
    if (parsed) {
      this.hours = parsed.h;
      this.minutes = parsed.m;
      this._hasValue = true;
      this.emitChange();
    }
  }

  private parseTime(value: string): { h: number; m: number } | null {
    const match = value.match(/^(\d{1,2}):(\d{2})$/);
    if (match) {
      const h = Number(match[1]);
      const m = Number(match[2]);
      if (h >= 0 && h <= 23 && m >= 0 && m <= 59) return { h, m };
    }
    return null;
  }

  // ── Interactions ──────────────────────────────────────────────

  toggleOpen(event: MouseEvent): void {
    event.stopPropagation();
    if (this._disabled) return;
    this.open.update((v) => !v);
    if (this.open()) {
      this._hasValue = true;
      this.onTouched();
    }
    this.cdr.markForCheck();
  }

  incrementHours(): void {
    if (this._disabled) return;
    this.hours = (this.hours + 1) % 24;
    this._hasValue = true;
    this.emitChange();
  }

  decrementHours(): void {
    if (this._disabled) return;
    this.hours = (this.hours - 1 + 24) % 24;
    this._hasValue = true;
    this.emitChange();
  }

  incrementMinutes(): void {
    if (this._disabled) return;
    this.minutes = (this.minutes + 1) % 60;
    this._hasValue = true;
    this.emitChange();
  }

  decrementMinutes(): void {
    if (this._disabled) return;
    this.minutes = (this.minutes - 1 + 60) % 60;
    this._hasValue = true;
    this.emitChange();
  }

  setNow(): void {
    const now = new Date();
    this.hours = now.getHours();
    this.minutes = now.getMinutes();
    this._hasValue = true;
    this.emitChange();
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  confirmTime(): void {
    this.open.set(false);
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  private emitChange(): void {
    const h = String(this.hours).padStart(2, '0');
    const m = String(this.minutes).padStart(2, '0');
    this.onChange(`${h}:${m}`);
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.open()) return;
    if (!this.elRef.nativeElement.contains(event.target)) {
      this.open.set(false);
      this.cdr.markForCheck();
    }
  }

  @HostListener('keydown', ['$event'])
  onKeyDown(event: KeyboardEvent): void {
    if (!this.open()) return;
    if (event.key === 'Escape') {
      this.open.set(false);
      this.cdr.markForCheck();
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.incrementHours();
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.decrementHours();
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      this.incrementMinutes();
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      this.decrementMinutes();
    }
  }
}
