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
  selector: 'ui-date-picker',
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DatePickerComponent),
      multi: true,
    },
  ],
  templateUrl: './date-picker.component.html',
  styleUrl: './date-picker.component.scss',
})
export class DatePickerComponent implements ControlValueAccessor {
  @Input() label = '';
  @Input() id = '';
  @Input() hasError = false;

  private readonly cdr = inject(ChangeDetectorRef);
  private readonly elRef = inject(ElementRef);

  readonly open = signal(false);

  // Internal state
  selectedYear = 0;
  selectedMonth = 0; // 0-based
  selectedDay = 0;

  viewYear = new Date().getFullYear();
  viewMonth = new Date().getMonth();

  inputFocused = false;
  inputValue = '';
  inputError = false;

  private _disabled = false;

  onChange: (v: string) => void = () => {};
  onTouched: () => void = () => {};

  // ── ControlValueAccessor ──────────────────────────────────────

  writeValue(v: string): void {
    if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
      const [y, m, d] = v.split('-').map(Number);
      this.selectedYear = y;
      this.selectedMonth = m - 1;
      this.selectedDay = d;
      this.viewYear = y;
      this.viewMonth = m - 1;
    } else {
      this.selectedYear = 0;
      this.selectedMonth = 0;
      this.selectedDay = 0;
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
    if (!this.selectedDay) return '';
    const y = this.selectedYear;
    const m = String(this.selectedMonth + 1).padStart(2, '0');
    const d = String(this.selectedDay).padStart(2, '0');
    return `${d}.${m}.${y}`;
  }

  get monthLabel(): string {
    const date = new Date(this.viewYear, this.viewMonth, 1);
    return date.toLocaleString('en-US', { month: 'long', year: 'numeric' });
  }

  get calendarDays(): (number | null)[] {
    const firstDay = new Date(this.viewYear, this.viewMonth, 1).getDay();
    // Shift so week starts on Monday
    const startOffset = (firstDay + 6) % 7;
    const daysInMonth = new Date(this.viewYear, this.viewMonth + 1, 0).getDate();
    const cells: (number | null)[] = [];
    for (let i = 0; i < startOffset; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    return cells;
  }

  get weekDays(): string[] {
    return ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  }

  isSelected(day: number): boolean {
    return (
      this.selectedDay === day &&
      this.selectedMonth === this.viewMonth &&
      this.selectedYear === this.viewYear
    );
  }

  isToday(day: number): boolean {
    const t = new Date();
    return (
      t.getDate() === day && t.getMonth() === this.viewMonth && t.getFullYear() === this.viewYear
    );
  }

  isPast(day: number): boolean {
    const d = new Date(this.viewYear, this.viewMonth, day);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return d < today;
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
    // Try to parse on blur
    this.tryParseInput(this.inputValue);
    // Reset to display value
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  onInputChange(value: string): void {
    const digits = value.replace(/\D/g, '');
    let formatted: string;
    if (digits.length <= 2) {
      formatted = digits;
    } else if (digits.length <= 4) {
      formatted = `${digits.slice(0, 2)}.${digits.slice(2, 4)}`;
    } else {
      formatted = `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4, 8)}`;
    }
    formatted = formatted.slice(0, 10);
    this.inputValue = formatted;

    if (digits.length === 8) {
      const d = Number(digits.slice(0, 2));
      const m = Number(digits.slice(2, 4));
      const y = Number(digits.slice(4, 8));
      if (m >= 1 && m <= 12 && d >= 1 && d <= 31) {
        this.selectedDay = d;
        this.selectedMonth = m - 1;
        this.selectedYear = y;
        this.viewMonth = m - 1;
        this.viewYear = y;
        const mm = String(m).padStart(2, '0');
        const dd = String(d).padStart(2, '0');
        this.onChange(`${y}-${mm}-${dd}`);
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
    const parsed = this.parseDate(value);
    if (parsed) {
      this.selectedYear = parsed.y;
      this.selectedMonth = parsed.m - 1;
      this.selectedDay = parsed.d;
      this.viewYear = parsed.y;
      this.viewMonth = parsed.m - 1;
      const mm = String(parsed.m).padStart(2, '0');
      const dd = String(parsed.d).padStart(2, '0');
      this.onChange(`${parsed.y}-${mm}-${dd}`);
    }
  }

  private parseDate(value: string): { y: number; m: number; d: number } | null {
    // dd.mm.yyyy
    const dmyMatch = value.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (dmyMatch) {
      const d = Number(dmyMatch[1]);
      const m = Number(dmyMatch[2]);
      const y = Number(dmyMatch[3]);
      if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return { y, m, d };
    }
    // yyyy-mm-dd
    const ymdMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (ymdMatch) {
      const y = Number(ymdMatch[1]);
      const m = Number(ymdMatch[2]);
      const d = Number(ymdMatch[3]);
      if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return { y, m, d };
    }
    return null;
  }

  // ── Interactions ──────────────────────────────────────────────

  toggleOpen(event: MouseEvent): void {
    event.stopPropagation();
    if (this._disabled) return;
    this.open.update((v) => !v);
    if (this.open()) this.onTouched();
    this.cdr.markForCheck();
  }

  prevMonth(): void {
    if (this.viewMonth === 0) {
      this.viewMonth = 11;
      this.viewYear--;
    } else {
      this.viewMonth--;
    }
    this.cdr.markForCheck();
  }

  nextMonth(): void {
    if (this.viewMonth === 11) {
      this.viewMonth = 0;
      this.viewYear++;
    } else {
      this.viewMonth++;
    }
    this.cdr.markForCheck();
  }

  setToday(): void {
    const now = new Date();
    this.selectedYear = now.getFullYear();
    this.selectedMonth = now.getMonth();
    this.selectedDay = now.getDate();
    this.viewYear = this.selectedYear;
    this.viewMonth = this.selectedMonth;
    const m = String(this.selectedMonth + 1).padStart(2, '0');
    const d = String(this.selectedDay).padStart(2, '0');
    this.onChange(`${this.selectedYear}-${m}-${d}`);
    this.inputValue = this.displayValue;
    this.cdr.markForCheck();
  }

  selectDay(day: number | null): void {
    if (!day) return;
    this.selectedDay = day;
    this.selectedMonth = this.viewMonth;
    this.selectedYear = this.viewYear;
    const m = String(this.viewMonth + 1).padStart(2, '0');
    const d = String(day).padStart(2, '0');
    this.onChange(`${this.viewYear}-${m}-${d}`);
    this.inputValue = this.displayValue;
    this.open.set(false);
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
    if (!this.selectedDay) return;
    const current = new Date(this.selectedYear, this.selectedMonth, this.selectedDay);
    let delta = 0;
    if (event.key === 'ArrowLeft') delta = -1;
    if (event.key === 'ArrowRight') delta = 1;
    if (event.key === 'ArrowUp') delta = -7;
    if (event.key === 'ArrowDown') delta = 7;
    if (delta !== 0) {
      event.preventDefault();
      current.setDate(current.getDate() + delta);
      this.selectedYear = current.getFullYear();
      this.selectedMonth = current.getMonth();
      this.selectedDay = current.getDate();
      this.viewYear = this.selectedYear;
      this.viewMonth = this.selectedMonth;
      const m = String(this.selectedMonth + 1).padStart(2, '0');
      const d = String(this.selectedDay).padStart(2, '0');
      this.onChange(`${this.selectedYear}-${m}-${d}`);
      this.inputValue = this.displayValue;
      this.cdr.markForCheck();
    }
  }
}
