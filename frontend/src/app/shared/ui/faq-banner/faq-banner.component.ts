import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'ui-faq-banner',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './faq-banner.component.html',
  styleUrl: './faq-banner.component.scss',
})
export class FaqBannerComponent {
  @Input() text = 'STILL HAVE QUESTIONS? VISIT FAQ';
  @Input() link = '/faq';
  @Input() ariaLabel = 'Visit FAQ';
}
