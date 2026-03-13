import React from 'react';

type ModeCard = {
  title: string;
  description: string;
  controls?: React.ReactNode;
};

type ModeCardsRowProps = {
  cards: [ModeCard, ModeCard, ModeCard];
};

export function ModeCardsRow({ cards }: ModeCardsRowProps) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {cards.map((card) => (
        <section
          key={card.title}
          className="flex flex-col gap-3 border-2 border-lawn-border bg-lawn-bg p-3 shadow-brutal-sm"
        >
          <div className="border-2 border-lawn-border bg-lawn-panel p-3">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-lawn-muted">
              {card.title}
            </p>
            <p className="mt-2 text-sm font-bold leading-5 text-lawn-border">
              {card.description}
            </p>
          </div>
          {card.controls ? <div className="space-y-3">{card.controls}</div> : null}
        </section>
      ))}
    </div>
  );
}
