import gsbg

profile = "https://scholar.google.com/citations?user=YOUR_ID&hl=en"

gsbg.gene_citation_badge_svg(
    link=profile,
    link_type="profile",
    svg_name="citations.svg",
    path_to_save="figs",
)
# add more calls for h-index/i10 if the API supports them
