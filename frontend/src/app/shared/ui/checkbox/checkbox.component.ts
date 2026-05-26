import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  forwardRef,
  inject,
  Input,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'ui-checkbox',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CheckboxComponent),
      multi: true,
    },
  ],
  templateUrl: './checkbox.component.html',
  styleUrl: './checkbox.component.scss',
})
export class CheckboxComponent implements ControlValueAccessor {
  @Input() label = '';
  @Input() id = '';

  _checked = false;
  _disabled = false;
  private readonly cdr = inject(ChangeDetectorRef);

  onChange: (v: boolean) => void = () => {};
  onTouched: () => void = () => {};

  writeValue(v: boolean): void {
    this._checked = !!v;
    this.cdr.markForCheck();
  }

  registerOnChange(fn: (v: boolean) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this._disabled = isDisabled;
    this.cdr.markForCheck();
  }

  toggle(): void {
    if (this._disabled) return;
    this._checked = !this._checked;
    this.onChange(this._checked);
    this.onTouched();
  }
}
