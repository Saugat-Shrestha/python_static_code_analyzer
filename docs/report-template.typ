// Pandoc template for the PRT582 report.
// Layout follows the unit's expected report format: running header with the
// unit name and page number, and a "-- n of N --" footer.

#let horizontalrule = line(start: (25%, 0%), end: (75%, 0%), stroke: 0.5pt + rgb("#cccccc"))

#show terms: it => {
  it.children
    .map(child => [
      #strong[#child.term]
      #block(inset: (left: 1.5em, top: -0.4em))[#child.description]
    ])
    .join()
}

#set page(
  paper: "a4",
  margin: (top: 2.6cm, bottom: 2.2cm, left: 2.1cm, right: 2.1cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(size: 9pt, fill: rgb("#4a4a4a"))
      #grid(
        columns: (1fr, auto),
        align(left)[PRT582 -- Software Development Project],
        align(right)[Page #counter(page).display()],
      )
      #v(-7pt)
      #line(length: 100%, stroke: 0.5pt + rgb("#c8c8c8"))
    ]
  },
  footer: context {
    if counter(page).get().first() > 1 [
      #set text(size: 9pt, fill: rgb("#4a4a4a"))
      #align(center)[-- #counter(page).display() of #counter(page).final().first() --]
    ]
  },
)

#set text(font: ("Helvetica Neue", "Helvetica", "Arial", "Liberation Sans"), size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.68em, spacing: 0.9em)
#show link: it => text(fill: rgb("#1155cc"))[#it]

// The document title sits on the cover page, so keep it out of the contents.
#show heading.where(level: 1): set heading(outlined: false)
#show heading.where(level: 1): it => {
  block(above: 1.5em, below: 0.7em)[#text(size: 15pt, weight: "bold", fill: rgb("#1a1a1a"))[#it.body]]
}
#show heading.where(level: 2): it => {
  block(above: 1.5em, below: 0.7em)[#text(size: 15pt, weight: "bold", fill: rgb("#1a1a1a"))[#it.body]]
}
#show heading.where(level: 3): it => {
  block(above: 1.2em, below: 0.55em)[#text(size: 12pt, weight: "bold", fill: rgb("#2a2a2a"))[#it.body]]
}
#show heading.where(level: 4): it => {
  block(above: 1em, below: 0.45em)[#text(size: 10.5pt, weight: "bold", style: "italic")[#it.body]]
}

#show raw.where(block: true): it => block(
  width: 100%,
  fill: rgb("#f6f6f6"),
  stroke: 0.5pt + rgb("#dcdcdc"),
  radius: 2pt,
  inset: 7pt,
  breakable: true,
)[#set text(size: 7.6pt, font: ("Menlo", "DejaVu Sans Mono", "Courier New")); #set par(justify: false, leading: 0.5em); #it]

#show raw.where(block: false): it => box(
  fill: rgb("#f0f0f0"),
  outset: (y: 2.5pt),
  inset: (x: 2.5pt),
  radius: 1.5pt,
)[#text(size: 0.87em, font: ("Menlo", "DejaVu Sans Mono", "Courier New"))[#it]]

#set table(
  inset: 5.5pt,
  stroke: 0.5pt + rgb("#c8c8c8"),
)
#show table.cell.where(y: 0): set text(weight: "bold", size: 9pt)
#show table: set text(size: 8.5pt)
#show table: set par(justify: false, leading: 0.5em)

#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: image): set figure.caption(position: bottom)
#show figure.caption: set text(size: 9pt, style: "italic")

#set quote(block: true)
#show quote: it => block(
  width: 100%,
  inset: (left: 10pt, top: 5pt, bottom: 5pt),
  stroke: (left: 2.5pt + rgb("#c0c0c0")),
)[#it.body]

#set list(indent: 0.6em, spacing: 0.75em)
#set enum(indent: 0.6em, spacing: 0.75em)

$if(title)$
#set document(title: [$title$]$if(author)$, author: ($for(author)$[$author$]$sep$, $endfor$)$endif$)
$endif$

$for(header-includes)$
$header-includes$

$endfor$
$body$
