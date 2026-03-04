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
          className="border-2 border-lawn-border bg-lawn-bg p-4 shadow-brutal-sm"
        >
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-stone-500">
            {card.title}
          </p>
          <p className="mt-2 text-sm font-bold leading-5 text-lawn-border">
            {card.description}
          </p>
          {card.controls ? <div className="mt-3 space-y-3">{card.controls}</div> : null}
        </section>
      ))}
    </div>
  );
}
