import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../shared/layout/public-footer/public-footer.component';
import { ScrollToTopComponent } from '../../shared/ui/scroll-to-top/scroll-to-top.component';

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqGroup {
  topic: string;
  items: FaqItem[];
}

@Component({
  selector: 'app-faq',
  standalone: true,
  imports: [CommonModule, RouterLink, TranslatePipe, PublicHeaderComponent, PublicFooterComponent, ScrollToTopComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './faq.component.html',
  styleUrl: './faq.component.scss',
})
export class FaqComponent {
  readonly openIndex = signal<string | null>(null);

  readonly groups: FaqGroup[] = [
    {
      topic: 'faq.groups.gettingStarted.topic',
      items: [
        { question: 'faq.groups.gettingStarted.q1.q', answer: 'faq.groups.gettingStarted.q1.a' },
        { question: 'faq.groups.gettingStarted.q2.q', answer: 'faq.groups.gettingStarted.q2.a' },
        { question: 'faq.groups.gettingStarted.q3.q', answer: 'faq.groups.gettingStarted.q3.a' },
      ],
    },
    {
      topic: 'faq.groups.forVoters.topic',
      items: [
        { question: 'faq.groups.forVoters.q1.q', answer: 'faq.groups.forVoters.q1.a' },
        { question: 'faq.groups.forVoters.q2.q', answer: 'faq.groups.forVoters.q2.a' },
        { question: 'faq.groups.forVoters.q3.q', answer: 'faq.groups.forVoters.q3.a' },
        { question: 'faq.groups.forVoters.q4.q', answer: 'faq.groups.forVoters.q4.a' },
      ],
    },
    {
      topic: 'faq.groups.forOrganizers.topic',
      items: [
        { question: 'faq.groups.forOrganizers.q1.q', answer: 'faq.groups.forOrganizers.q1.a' },
        { question: 'faq.groups.forOrganizers.q2.q', answer: 'faq.groups.forOrganizers.q2.a' },
        { question: 'faq.groups.forOrganizers.q3.q', answer: 'faq.groups.forOrganizers.q3.a' },
      ],
    },
    {
      topic: 'faq.groups.results.topic',
      items: [
        { question: 'faq.groups.results.q1.q', answer: 'faq.groups.results.q1.a' },
        { question: 'faq.groups.results.q2.q', answer: 'faq.groups.results.q2.a' },
        { question: 'faq.groups.results.q3.q', answer: 'faq.groups.results.q3.a' },
      ],
    },
    {
      topic: 'faq.groups.security.topic',
      items: [
        { question: 'faq.groups.security.q1.q', answer: 'faq.groups.security.q1.a' },
        { question: 'faq.groups.security.q2.q', answer: 'faq.groups.security.q2.a' },
        { question: 'faq.groups.security.q3.q', answer: 'faq.groups.security.q3.a' },
      ],
    },
  ];

  toggle(key: string): void {
    this.openIndex.update((current) => (current === key ? null : key));
  }

  isOpen(key: string): boolean {
    return this.openIndex() === key;
  }

  trackByIndex(_: number, item: FaqItem): string {
    return item.question;
  }
}
