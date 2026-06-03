import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';

export type StepCardVariant = 'white' | 'lime' | 'purple' | 'outlined-dark';

@Component({
  selector: 'ui-step-card',
  standalone: true,
  imports: [TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './step-card.component.html',
  styleUrl: './step-card.component.scss',
  host: {
    '[attr.variant]': 'variant',
  },
})
export class StepCardComponent {
  @Input({ required: true }) step!: number;
  @Input({ required: true }) title!: string;
  @Input({ required: true }) description!: string;
  @Input() variant: StepCardVariant = 'white';
}
