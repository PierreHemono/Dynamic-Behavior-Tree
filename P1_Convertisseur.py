#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Lire le fichier solution.sol
with open('/home/admin-local/Projets_Python/modèle FJSP - THESE/CodeFJSP/solution.sol', 'r') as file:
    lines = file.readlines()

# Initialiser un dictionnaire pour stocker les valeurs Sijk, Cijk, et Xijk
operation_times = {}

# Fonction pour arrondir les valeurs
def round_value(value):
    if abs(value) < 1e-3:  # Mettre à zéro si la valeur est inférieure à 0.001
        return 0
    else:
        return round(value)  # Arrondir au plus proche pour les autres valeurs

# Parcourir les lignes et extraire les variables Sijk, Cijk, et Xijk
for line in lines:
    if line.startswith('Sijk') or line.startswith('Cijk') or line.startswith('Xijk'):
        parts = line.strip().split(' ')
        var_name = parts[0]  # Nom de la variable
        value = round_value(float(parts[1]))  # Arrondir la valeur

        # Extraire les indices i, j, k de la variable (par exemple, Sijk[op_1,job_1,resource_1])
        indices = var_name.split('[')[1].split(']')[0]
        j, i, k = indices.split(',')  # Job, Operation, Resource

        # Conserver uniquement les informations Sijk (temps de début), Cijk (temps de fin), et Xijk (opération active)
        if (i, j, k) not in operation_times:
            operation_times[(i, j, k)] = {}

        # Stocker les valeurs de Sijk, Cijk, et Xijk
        if 'Sijk' in var_name:
            operation_times[(i, j, k)]['start'] = value
        elif 'Cijk' in var_name:
            operation_times[(i, j, k)]['end'] = value
        elif 'Xijk' in var_name and value > 0.5:  # Ne conserver que les opérations actives
            operation_times[(i, j, k)]['active'] = True

# Supprimer les opérations dont le temps de démarrage est égal au temps de fin ou inactives
filtered_operations = {key: val for key, val in operation_times.items() if val.get('start', 0) != val.get('end', 0) and val.get('active', False)}

# Filtrer les opérations en supprimant celles associées à H ou R si une opération Co existe
filtered_operations_final = {}
for (i, j, k), times in filtered_operations.items():
    # Vérifier si une opération collaborative (CO) existe déjà
    co_key = (i, j, 'Co')
    if co_key in filtered_operations:
        # Si une opération CO existe, ne conserver que celle-ci
        if (i, j, k) == co_key:
            filtered_operations_final[(i, j, k)] = times
    else:
        # Sinon, conserver l'opération actuelle
        filtered_operations_final[(i, j, k)] = times

# Trier les opérations par ordre croissant de Sijk (start time)
sorted_operations = sorted(filtered_operations_final.items(), key=lambda x: x[1]['start'])

# Écrire les résultats triés dans un fichier plus lisible
with open('/home/admin-local/Projets_Python/modèle FJSP - THESE/CodeFJSP/solution_readable.txt', 'w') as file:
    file.write("Operations sorted by start time (Sijk) and end time (Cijk):\n\n")
    for (i, j, k), times in sorted_operations:
        file.write("Operation {}, Job {}, Resource {}: Start time (Sijk) = {}, End time (Cijk) = {}\n".format(j, i, k, times['start'], times['end']))

print("Processing completed. The filtered and sorted operations are saved in solution_readable.txt.")
