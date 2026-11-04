-- Staging : typage, renommage et reconstitution de la période de contact.
--
-- Le fichier source est trié par date (mai 2008 -> novembre 2010) mais ne contient
-- que le mois. L'année est reconstituée en incrémentant un compteur à chaque fois
-- que le mois "recule" d'une ligne à la suivante (ex. décembre -> mars).

CREATE OR REPLACE TABLE stg_contacts AS
-- `raw_contacts` est le CSV source chargé tel quel, avec `contact_id` = numéro de ligne
-- (voir warehouse.py : l'ordre des lignes porte l'information de date).
WITH typed AS (
    SELECT
        contact_id,
        CAST(age AS INTEGER)                         AS age,
        job,
        marital,
        education,
        "default"                                    AS credit_default,
        housing                                      AS housing_loan,
        loan                                         AS personal_loan,
        contact                                      AS channel,
        month                                        AS month_abbr,
        CASE month
            WHEN 'jan' THEN 1 WHEN 'feb' THEN 2 WHEN 'mar' THEN 3 WHEN 'apr' THEN 4
            WHEN 'may' THEN 5 WHEN 'jun' THEN 6 WHEN 'jul' THEN 7 WHEN 'aug' THEN 8
            WHEN 'sep' THEN 9 WHEN 'oct' THEN 10 WHEN 'nov' THEN 11 WHEN 'dec' THEN 12
        END                                          AS month_num,
        day_of_week,
        CAST(duration AS INTEGER)                    AS call_duration_s,
        CAST(campaign AS INTEGER)                    AS calls_this_campaign,
        CASE WHEN pdays = 999 THEN NULL ELSE CAST(pdays AS INTEGER) END AS days_since_prev_contact,
        CAST(previous AS INTEGER)                    AS prev_contacts,
        poutcome                                     AS prev_outcome,
        CAST("emp.var.rate" AS DOUBLE)               AS emp_var_rate,
        CAST("cons.price.idx" AS DOUBLE)             AS cons_price_idx,
        CAST("cons.conf.idx" AS DOUBLE)              AS cons_conf_idx,
        CAST(euribor3m AS DOUBLE)                    AS euribor_3m,
        CAST("nr.employed" AS DOUBLE)                AS nr_employed,
        (y = 'yes')                                  AS subscribed
    FROM raw_contacts
),
year_breaks AS (
    SELECT
        *,
        CASE WHEN month_num < lag(month_num) OVER (ORDER BY contact_id) THEN 1 ELSE 0 END
            AS new_year
    FROM typed
)
SELECT
    * EXCLUDE (new_year),
    CAST(2008 + sum(new_year) OVER (ORDER BY contact_id ROWS UNBOUNDED PRECEDING) AS INTEGER) AS year
FROM year_breaks;
