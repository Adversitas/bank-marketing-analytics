-- Modèle en étoile : une table de faits (un contact = un client appelé dans une
-- campagne) et des dimensions avec libellés français pour la restitution.

CREATE OR REPLACE TABLE dim_period AS
SELECT
    year * 100 + month_num                                   AS period_id,
    year,
    month_num,
    make_date(year, month_num, 1)                            AS month_start,
    strftime(make_date(year, month_num, 1), '%Y-%m')         AS period_label,
    -- Indicateurs macro-économiques (Banque du Portugal) : moyenne du mois.
    round(avg(euribor_3m), 3)                                AS euribor_3m,
    round(avg(emp_var_rate), 2)                              AS emp_var_rate,
    round(avg(cons_conf_idx), 1)                             AS cons_conf_idx,
    round(avg(cons_price_idx), 3)                            AS cons_price_idx
FROM stg_contacts
GROUP BY ALL;

CREATE OR REPLACE TABLE dim_job (job VARCHAR PRIMARY KEY, job_fr VARCHAR, job_group VARCHAR);
INSERT INTO dim_job VALUES
    ('admin.',        'Employé administratif',   'Actifs'),
    ('blue-collar',   'Ouvrier',                 'Actifs'),
    ('entrepreneur',  'Chef d''entreprise',      'Indépendants'),
    ('housemaid',     'Employé de maison',       'Actifs'),
    ('management',    'Cadre',                   'Actifs'),
    ('retired',       'Retraité',                'Inactifs'),
    ('self-employed', 'Indépendant',             'Indépendants'),
    ('services',      'Employé des services',    'Actifs'),
    ('student',       'Étudiant',                'Inactifs'),
    ('technician',    'Technicien',              'Actifs'),
    ('unemployed',    'Sans emploi',             'Inactifs'),
    ('unknown',       'Non renseigné',           'Non renseigné');

CREATE OR REPLACE TABLE dim_education (education VARCHAR PRIMARY KEY, education_fr VARCHAR, rank INTEGER);
INSERT INTO dim_education VALUES
    ('illiterate',          'Sans diplôme',            0),
    ('basic.4y',            'Primaire (4 ans)',        1),
    ('basic.6y',            'Primaire (6 ans)',        2),
    ('basic.9y',            'Collège (9 ans)',         3),
    ('high.school',         'Lycée',                   4),
    ('professional.course', 'Formation professionnelle', 5),
    ('university.degree',   'Diplôme universitaire',   6),
    ('unknown',             'Non renseigné',           99);

CREATE OR REPLACE TABLE fact_contact AS
SELECT
    c.contact_id,
    c.year * 100 + c.month_num AS period_id,
    c.day_of_week,
    c.channel,
    c.age,
    CASE
        WHEN c.age < 25 THEN '18-24'
        WHEN c.age < 35 THEN '25-34'
        WHEN c.age < 45 THEN '35-44'
        WHEN c.age < 55 THEN '45-54'
        WHEN c.age < 65 THEN '55-64'
        ELSE '65+'
    END AS age_band,
    c.job,
    c.marital,
    c.education,
    c.credit_default,
    c.housing_loan,
    c.personal_loan,
    c.calls_this_campaign,
    c.prev_contacts,
    c.days_since_prev_contact,
    c.prev_outcome,
    c.call_duration_s,
    c.subscribed
FROM stg_contacts c;
