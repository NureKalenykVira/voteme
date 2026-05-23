import {
  ChangeDetectionStrategy,
  Component,
  Input,
} from '@angular/core';

@Component({
  selector: 'app-hero-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hero-card.component.html',
  styleUrl: './hero-card.component.scss',
  host: {
    '[attr.tone]': 'tone',
  },
})
export class HeroCardComponent {
  @Input() tone: 'purple' | 'lime' = 'purple';
}
