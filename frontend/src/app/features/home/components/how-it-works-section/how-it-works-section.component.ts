import { NgFor } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  StepCardComponent,
  StepCardVariant,
} from '../../../../shared/ui/step-card/step-card.component';

interface Step {
  step: number;
  title: string;
  description: string;
  variant: StepCardVariant;
}

@Component({
  selector: 'app-how-it-works-section',
  standalone: true,
  imports: [NgFor, RouterLink, StepCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './how-it-works-section.component.html',
  styleUrl: './how-it-works-section.component.scss',
})
export class HowItWorksSectionComponent {
  readonly steps: Step[] = [
    {
      step: 1,
      title: 'Create a voting',
      description: 'Set a title, description, deadline and access rules for your election',
      variant: 'white',
    },
    {
      step: 2,
      title: 'Invite voters',
      description: 'Share a unique link, access code or QR with your participants',
      variant: 'lime',
    },
    {
      step: 3,
      title: 'Cast your vote',
      description:
        'Voters join securely, fill the ballot and submit — protected from double voting',
      variant: 'purple',
    },
    {
      step: 4,
      title: 'Verify results',
      description: 'Results are recorded on Ethereum blockchain and open for public verification',
      variant: 'outlined-dark',
    },
  ];
}
