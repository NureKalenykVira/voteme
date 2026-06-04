import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'ui-faq-banner',
  standalone: true,
  imports: [RouterLink, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './faq-banner.component.html',
  styleUrl: './faq-banner.component.scss',
})
export class FaqBannerComponent {
  @Input() text = 'faq.bannerText';
  @Input() link = '/faq';
  @Input() ariaLabel = 'Visit FAQ';
}
