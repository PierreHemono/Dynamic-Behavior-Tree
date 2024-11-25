#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import sys

# Chemins des fichiers
operations_file = '/home/admin-local/Projets_Python/modèle FJSP - THESE/CodeFJSP/operations_elementaires.json'
logs_file = '/home/admin-local/Projets_Python/modèle FJSP - THESE/CodeFJSP/solution_readable.txt'
domain_file_path = '/home/admin-local/Projets_Python/modèle FJSP - THESE/CodeFJSP/domain.pddl'
problem_file_path = '/home/admin-local/Projets_Python/modèle FJSP - THESE/CodeFJSP/problem.pddl'

# Charger les opérations élémentaires depuis le fichier JSON
try:
    with open(operations_file, 'r') as json_file:
        operations_elementaires = json.load(json_file)
except Exception as e:
    print("Erreur lors du chargement du fichier JSON :", e)
    sys.exit(1)

# Charger les logs de solution_readable.txt
try:
    with open(logs_file, 'r') as log_file:
        logs = log_file.readlines()
except Exception as e:
    print("Erreur lors du chargement du fichier de logs :", e)
    sys.exit(1)

# Regex pour extraire les informations des logs
log_pattern = r'Operation (\w+), Job (\w+), Resource (\w+): Start time \(Sijk\) = (\d+), End time \(Cijk\) = (\d+)'

# Initialisation des ensembles pour stocker les opérations filtrées et les outils
operations = []
operations_requiring_tools = set()
move_to_operations = set()
tools = set()
filtered_logs = []
locations = []
op_locations = {}
location_counter = 1

previous_end_time = None  # Pour détecter les attentes

# Analyse des logs et filtrage pour les ressources R et Co
for log in logs:
    match = re.match(log_pattern, log)
    if match:
        op_id = match.group(1)  # Exemple : 'op_2'
        job_id = match.group(2)  # Exemple : 'j_2'
        resource = match.group(3)  # Exemple : 'R' ou 'Co'
        start_time = int(match.group(4))
        end_time = int(match.group(5))

        # Filtrer uniquement les opérations par ressource R ou Co
        if resource in ['R', 'Co']:
            if '_' in op_id and '_' in job_id:
                # Extraire les numéros après '_'
                op_num = op_id.split('_')[1]
                job_num = job_id.split('_')[1]

                # Ajouter un suffixe _CO si la ressource est Co
                suffix = "_CO" if resource == "Co" else ""

                # Générer le nom de l'opération au format OPxx
                op_name = "OP" + job_num + op_num + suffix
                operations.append((op_name, job_id, resource, start_time, end_time))
                filtered_logs.append((op_name, job_id, resource, start_time, end_time))

                # Vérification si une attente est nécessaire
                if previous_end_time is not None and start_time > previous_end_time:
                    # Ajouter une action 'wait' si l'agent doit attendre
                    filtered_logs.append(("wait", job_id, resource, previous_end_time, start_time))
                previous_end_time = end_time

# Tri des opérations en fonction du temps de début
filtered_logs.sort(key=lambda x: x[3])

# Vérification des opérations filtrées
if not operations:
    print("Erreur : Aucune opération n'a été trouvée avec les ressources 'R' ou 'Co'.")
    sys.exit(1)

# Générer les outils associés et gérer les opérations 'move_to'
for op_entry in operations:
    op_name, job_id, resource, start_time, end_time = op_entry
    # On cherche l'opération correspondante dans le fichier JSON
    actions = operations_elementaires["jobs"].get(job_id, {}).get("operations", {}).get(op_name.replace("_CO", ""), [])
    # Si l'opération contient 'pick' ou 'place', on ajoute l'outil associé
    if "pick" in actions or "place" in actions:
        tool_name = "tool_" + op_name.lower()
        tools.add(tool_name)
        operations_requiring_tools.add(op_name)
    # Si l'opération contient 'move_to', on gère les locations
    if "move_to" in actions:
        move_to_name = "move_to_" + op_name.lower()
        move_to_operations.add(move_to_name)
        # Ajouter des locations dynamiques
        loc_from = "loc_{}".format(location_counter)
        location_counter += 1
        loc_to = "loc_{}".format(location_counter)
        location_counter += 1
        locations.append((move_to_name, loc_from, loc_to))
        # Stocker la location pour l'opération
        op_locations[op_name] = loc_to
    else:
        # Si pas de 'move_to', location par défaut
        op_locations[op_name] = "loc_workstation"

def generer_domain_pddl():
    try:
        with open(domain_file_path, 'w') as domain_file:
            domain_file.write("(define (domain specific_plan)\n")
            domain_file.write("  (:requirements :strips :typing)\n")
            domain_file.write("  (:types agent tool location operation)\n")
            
            # Ajout des prédicats logiques
            domain_file.write("  (:predicates\n")
            domain_file.write("    (at ?a - agent ?l - location)\n")
            domain_file.write("    (move_to_workstation_done ?a - agent)\n")
            domain_file.write("    (move_to_done ?a - agent)\n")
            domain_file.write("    (holding ?a - agent ?t - tool)\n")
            domain_file.write("    (tool_at ?t - tool ?l - location)\n")
            domain_file.write("    (can_operate ?t - tool ?op - operation)\n")
            domain_file.write("    (wait_done ?a - agent)\n")
            domain_file.write("    (pick_done ?a - agent)\n")
            domain_file.write("    (place_done ?a - agent)\n")
            
            # Prédicats pour chaque opération spécifique
            for op in sorted(operations_requiring_tools):
                domain_file.write("    (pick_" + op.lower() + "_done)\n")
                domain_file.write("    (place_" + op.lower() + "_done)\n")
            domain_file.write("  )\n")

            # Ajout des actions génériques
            domain_file.write("\n  ;; Action Générique de Déplacement\n")
            domain_file.write("  (:action move_to\n")
            domain_file.write("    :parameters (?a - agent ?from - location ?to - location)\n")
            domain_file.write("    :precondition (at ?a ?from)\n")
            domain_file.write("    :effect (and\n")
            domain_file.write("      (at ?a ?to)\n")
            domain_file.write("      (not (at ?a ?from))\n")
            domain_file.write("      (move_to_done ?a))\n")
            domain_file.write("  )\n\n")

            # Ajout de l'action spécifique de déplacement vers la station de travail
            domain_file.write("  ;; Action Spécifique de Déplacement vers la Station de Travail\n")
            domain_file.write("  (:action move_to_workstation\n")
            domain_file.write("    :parameters (?a - agent ?from - location ?to - location)\n")
            domain_file.write("    :precondition (at ?a ?from)\n")
            domain_file.write("    :effect (and\n")
            domain_file.write("      (at ?a ?to)\n")
            domain_file.write("      (not (at ?a ?from))\n")
            domain_file.write("      (move_to_workstation_done ?a))\n")
            domain_file.write("  )\n\n")

            # Ajout des actions spécifiques avec chaînage des préconditions
            previous_op_name = None
            previous_action_type = None

            for op_entry in filtered_logs:
                op_name, job_id, resource, start_time, end_time = op_entry
                if op_name == "wait":
                    domain_file.write("  ;; Action d'Attente\n")
                    domain_file.write("  (:action wait\n")
                    domain_file.write("    :parameters (?a - agent)\n")
                    if previous_op_name:
                        domain_file.write("    :precondition (and ({}))\n".format(previous_op_name))
                    else:
                        domain_file.write("    :precondition (and)\n")
                    domain_file.write("    :effect (wait_done ?a)\n")
                    domain_file.write("  )\n\n")
                    previous_op_name = "wait_done ?a"
                    previous_action_type = 'wait'
                else:
                    actions = operations_elementaires["jobs"].get(job_id, {}).get("operations", {}).get(op_name.replace("_CO", ""), [])
                    if "pick" in actions:
                        domain_file.write("  ;; Action Spécifique de Pick pour " + op_name + "\n")
                        domain_file.write("  (:action pick_" + op_name.lower() + "\n")
                        domain_file.write("    :parameters (?a - agent ?t - tool ?l - location)\n")
                        preconditions = "(tool_at ?t ?l) (can_operate ?t " + op_name.lower() + ") (at ?a ?l) (move_to_done ?a)"
                        if previous_op_name:
                            preconditions = "(" + previous_op_name + ") " + preconditions
                        domain_file.write("    :precondition (and " + preconditions + ")\n")
                        domain_file.write("    :effect (and\n")
                        domain_file.write("      (holding ?a ?t)\n")
                        domain_file.write("      (not (tool_at ?t ?l))\n")
                        domain_file.write("      (pick_" + op_name.lower() + "_done))\n")
                        domain_file.write("  )\n\n")
                        previous_op_name = "pick_" + op_name.lower() + "_done"
                        previous_action_type = 'pick'
                    if "place" in actions:
                        domain_file.write("  ;; Action Spécifique de Place pour " + op_name + "\n")
                        domain_file.write("  (:action place_" + op_name.lower() + "\n")
                        domain_file.write("    :parameters (?a - agent ?t - tool)\n")
                        preconditions = "(holding ?a ?t) (pick_" + op_name.lower() + "_done) (can_operate ?t " + op_name.lower() + ") (at ?a loc_workstation)"
                        domain_file.write("    :precondition (and " + preconditions + ")\n")
                        domain_file.write("    :effect (and\n")
                        domain_file.write("      (tool_at ?t loc_workstation)\n")
                        domain_file.write("      (not (holding ?a ?t))\n")
                        domain_file.write("      (place_" + op_name.lower() + "_done))\n")
                        domain_file.write("  )\n\n")
                        previous_op_name = "place_" + op_name.lower() + "_done"
                        previous_action_type = 'place'

            domain_file.write(")\n")
        print("Le fichier domain.pddl a été généré avec succès.")
    except Exception as e:
        print("Erreur lors de la génération de domain.pddl :", e)
        sys.exit(1)


# Générer le fichier problem.pddl
def generer_problem_pddl():
    try:
        with open(problem_file_path, 'w') as problem_file:
            problem_file.write("(define (problem specific_scenario)\n")
            problem_file.write("  (:domain specific_plan)\n")
            problem_file.write("  (:objects\n")
            
            # Ajout des outils pour les opérations filtrées
            if tools:
                problem_file.write("    " + " ".join(sorted(tools)) + " - tool\n")
            
            # Ajout des locations
            all_locations = set(["loc_base", "loc_workstation"])
            all_locations.update({loc for _, loc_from, loc_to in locations for loc in [loc_from, loc_to]})
            problem_file.write("    " + " ".join(sorted(all_locations)) + " - location\n")
            
            # Ajout des agents (seulement agent_r)
            problem_file.write("    agent_r - agent\n")
            
            # Ajout des opérations (uniquement les vraies opérations, pas les move_to)
            if operations_requiring_tools:
                problem_file.write("    " + " ".join(sorted(operations_requiring_tools)) + " - operation\n")
            
            problem_file.write("  )\n")
    
            # Section Init
            problem_file.write("  (:init\n")
            # Initialisation des outils
            if tools:
                for tool in sorted(tools):
                    problem_file.write("    (tool_at " + tool + " loc_workstation)\n")
            # Initialisation de l'agent
            problem_file.write("    (at agent_r loc_base)\n")
            # Ajout des préconditions can_operate
            for op in sorted(operations_requiring_tools):
                problem_file.write("    (can_operate tool_" + op.lower() + " " + op.lower() + ")\n")
            problem_file.write("  )\n")
    
            # Section Goal
            # Le goal est l'effet de la dernière opération à réaliser

            last_op = None
            # On parcourt les opérations dans l'ordre pour trouver la dernière opération
            for op_name, job_id, resource, start_time, end_time in reversed(filtered_logs):
                if op_name != "wait":
                    actions = operations_elementaires["jobs"].get(job_id, {}).get("operations", {}).get(op_name.replace("_CO", ""), [])
                    if "place" in actions and op_name in operations_requiring_tools:
                        last_op = op_name
                        problem_file.write("  (:goal (and\n")
                        problem_file.write("    (place_" + last_op.lower() + "_done)\n")
                        problem_file.write("  ))\n")
                        break
                    elif "move_to" in actions:
                        # Si la dernière opération est un move_to
                        loc = op_locations.get(op_name, "loc_workstation")
                        problem_file.write("  (:goal (and\n")
                        problem_file.write("    (at agent_r " + loc + ")\n")
                        problem_file.write("  ))\n")
                        last_op = op_name  # Mise à jour de last_op pour éviter un second goal
                        break
            if not last_op:
                # Si aucune opération n'est trouvée pour le goal
                problem_file.write("  (:goal (and\n")
                problem_file.write("    (at agent_r loc_workstation)\n")
                problem_file.write("  ))\n")

            problem_file.write(")\n")
        print("Le fichier problem.pddl a été généré avec succès.")
    except Exception as e:
        print("Erreur lors de la génération de problem.pddl :", e)
        sys.exit(1)

# Générer les fichiers domain.pddl et problem.pddl
generer_domain_pddl()
generer_problem_pddl()
