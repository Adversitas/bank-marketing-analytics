-- Vues d'indicateurs consommées par le tableau de bord et l'export Excel.

-- Suivi mensuel de l'activité commerciale.
CREATE OR REPLACE VIEW kpi_monthly AS
SELECT
    p.period_id,
    p.period_label,
    p.month_start,
    count(*)                                                  AS clients_contactes,
    sum(f.calls_this_campaign)                                AS appels,
    sum(f.subscribed::INT)                                    AS souscriptions,
    avg(f.subscribed::INT)                                    AS taux_souscription,
    sum(f.calls_this_campaign) / nullif(sum(f.subscribed::INT), 0) AS appels_par_souscription,
    avg(f.calls_this_campaign)                                AS pression_commerciale,
    avg((f.prev_contacts > 0)::INT)                           AS part_clients_deja_sollicites,
    avg((f.channel = 'cellular')::INT)                        AS part_mobile,
    avg(f.call_duration_s) / 60.0                             AS duree_moyenne_appel_min,
    any_value(p.euribor_3m)                                   AS euribor_3m,
    any_value(p.cons_conf_idx)                                AS confiance_consommateurs
FROM fact_contact f
JOIN dim_period p USING (period_id)
GROUP BY ALL
ORDER BY p.period_id;

-- Une ligne par client contacté, avec les libellés français, pour les analyses par segment.
CREATE OR REPLACE VIEW v_contacts AS
SELECT
    f.*,
    p.period_label,
    p.year,
    p.euribor_3m,
    j.job_fr,
    j.job_group,
    e.education_fr,
    e.rank AS education_rank,
    CASE f.marital
        WHEN 'married' THEN 'Marié(e)' WHEN 'single' THEN 'Célibataire'
        WHEN 'divorced' THEN 'Divorcé(e) / veuf(ve)' ELSE 'Non renseigné'
    END AS marital_fr,
    CASE f.channel WHEN 'cellular' THEN 'Mobile' ELSE 'Fixe' END AS channel_fr,
    CASE f.prev_outcome
        WHEN 'success' THEN 'Succès' WHEN 'failure' THEN 'Échec' ELSE 'Jamais contacté'
    END AS prev_outcome_fr,
    CASE
        WHEN f.calls_this_campaign >= 6 THEN '6+'
        ELSE CAST(f.calls_this_campaign AS VARCHAR)
    END AS calls_band
FROM fact_contact f
JOIN dim_period p USING (period_id)
JOIN dim_job j USING (job)
JOIN dim_education e USING (education);
