# 01b_merge_banxico.R - merge the weekly Banxico "Consulta Historica Sectorizada" exports into one file.
# Put every downloaded Consulta_Todos_Instrumentos_*.xls in mx_bond_flows/raw/banxico_weekly/.
# Output: mx_bond_flows/raw/mx_issue_holdings.csv  (date, series, maturity, outstanding, foreign; MXN millions)
source("R/00_config.R")
dir_in <- file.path(RAW, "banxico_weekly")
files <- list.files(dir_in, pattern = "\\.xlsx?$", full.names = TRUE)
stopifnot(length(files) > 0)

read_one <- function(f) {
  x <- read_excel(f, sheet = 1)
  names(x) <- c("date", "clave", "maturity", "A", "B", "C", "D", "E", "F", "G", "H", "resid", "foreign", "total")
  x %>% mutate(clave = trimws(as.character(clave)),
               date = dmy(as.character(date)), maturity = dmy(as.character(maturity)),
               across(c(foreign, total), as.numeric))
}
all <- bind_rows(lapply(files, read_one)) %>% distinct(date, clave, maturity, .keep_all = TRUE) %>%
  arrange(clave, maturity, date)

mbono <- all %>% filter(clave == "M") %>%
  transmute(date, series = paste0("M_", format(maturity, "%Y%m%d")), maturity,
            outstanding = total, foreign)
write_csv(mbono, file.path(RAW, "mx_issue_holdings.csv"))
write_csv(all, file.path(RAW, "mx_all_instruments_weekly.csv"))

cat(sprintf("merged %d files: %d weeks from %s to %s; %d Mbono series\n", length(files),
            n_distinct(mbono$date), min(mbono$date), max(mbono$date), n_distinct(mbono$series)))
# Series that disappear from the file = matured. Their last outstanding is the principal repaid.
gaps <- mbono %>% group_by(series) %>% summarise(first = min(date), last = max(date), maturity = first(maturity)) %>%
  arrange(maturity)
print(gaps, n = 100)
