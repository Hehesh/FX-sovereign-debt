# 01_fetch_data.R - pull the public series that can be fetched by URL.
# Banxico SIE tables are downloaded by hand (see README) because the SIE export is a form, not a URL.
source("R/00_config.R")
dir.create(RAW, showWarnings = FALSE, recursive = TRUE)

# FRED: USD/MXN (H.10 noon NY, MXN per USD), VIX close, US 2y, Brent, plus sensitivity series
fred_ids <- c("DEXMXUS", "VIXCLS", "DGS2", "DCOILBRENTEU", "T10Y2Y", "DFII10", "DTWEXBGS", "DEXBZUS")
for (id in fred_ids) {
  f <- file.path(RAW, paste0(id, "_fred.csv"))
  if (!file.exists(f)) {
    download.file(sprintf("https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s", id), f, quiet = TRUE)
    message("fetched ", id)
  }
}

# Banxico SIE API (free token at https://www.banxico.org.mx/SieAPIRest/service/v1/token)
# Fill BANXICO_TOKEN in .Renviron, then set the series ids found under each CA175 / CA134 line
# (click a row on the SIE page -> "Ver serie" shows the id, e.g. SF43718 is the FIX rate).
banxico_series <- function(ids, from = "1994-01-03", to = format(Sys.Date())) {
  tok <- Sys.getenv("BANXICO_TOKEN"); stopifnot(nzchar(tok))
  url <- sprintf("https://www.banxico.org.mx/SieAPIRest/service/v1/series/%s/datos/%s/%s",
                 paste(ids, collapse = ","), from, to)
  r <- GET(url, add_headers("Bmx-Token" = tok, Accept = "application/json")); stop_for_status(r)
  js <- content(r, as = "parsed")$bmx$series
  bind_rows(lapply(js, function(s) tibble(id = s$idSerie, title = s$titulo,
    date = dmy(sapply(s$datos, `[[`, "fecha")),
    value = as.numeric(gsub(",", "", sapply(s$datos, `[[`, "dato"))))))
}
if (nzchar(Sys.getenv("BANXICO_TOKEN"))) {
  fix <- banxico_series("SF43718")                         # FIX, MXN per USD, noon Mexico City
  write_csv(fix, file.path(RAW, "banxico_FIX.csv"))
  # TODO: add ids for CA175 "Bonos" (foreign holdings, daily) and CA134 "Bonos" total outstanding,
  # and a Mexican 2y rate for the policy control (e.g. 2y Mbono or TIIE swap from the SIE vector).
}
