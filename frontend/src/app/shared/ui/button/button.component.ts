import {
  ChangeDetectionStrategy,
  Component,
  Input,
} from '@angular/core';

@Component({
  selector: 'ui-button',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      [type]="type"
      [disabled]="disabled"
      class="btn"
      [class.btn--primary]="variant === 'primary'"
      [class.btn--outline-dark]="variant === 'outline-dark'"
      [class.btn--outline-light]="variant === 'outline-light'"
      [class.btn--md]="size === 'md'"
      [class.btn--lg]="size === 'lg'"
      [class.btn--full]="fullWidth"
    ><ng-content /></button>
  `,
  styleUrl: './button.component.scss',
})
export class ButtonComponent {
  @Input() variant: 'primary' | 'outline-dark' | 'outline-light' = 'primary';
  @Input() size: 'md' | 'lg' = 'md';
  @Input() type: 'button' | 'submit' = 'button';
  @Input() disabled = false;
  @Input() fullWidth = false;
}
