import streamlit as st
import pandas as pd

#
# Classe de Calculateur de charges de copropriété
#

class Lot:
    """
    Classe d'objet permettant de définir un lot de copropriété avec ses ID et ses tantièles associés aux subdivisions.
    """
    def __init__(self, IDCommercial, IDNotaire, DicoTaxonomieTantiemes):
        self.IDNotaire = IDNotaire

        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Label des subdivisions': DicoTaxonomieTantiemes.value(),
            'ID des subdivisions': DicoTaxonomieTantiemes.keys(),
            'Tantiemes':0
        }
        self.DfTantiemes= pd.DataFrame(tableauTantiemesInitialise)

    def DefinirTantiemes(self, LabelDeSubdivision, Tantiemes):#Faire un dico plutôt
        self.DfTantiemes.loc[self.DfTantiemes['Label des subdivisions'] == LabelDeSubdivision, 'Tantiemes'] = Tantiemes

class Prestation:
    """
    Classe d'objet permettant de définir une prestation de copropriété avec son nom et son coût associé.
    """
    def __init__(self, Nom, Cout,Description,ID=None):
        self.Nom = Nom
        self.Cout = Cout
        self.Description = Description
        self.ID = ID

class Provision:
    """
    Classe d'objet permettant de définir une prestation de copropriété avec son nom et son coût associé.
    """
    def __init__(self, Nom, Provision,Description,TopConsommationChauffage=False,ID=None):
        self.Nom = Nom
        self.Provision = Provision
        self.Description = Description
        self.ID = ID
        self.TopConsommationChauffage=TopConsommationChauffage

class CalculateurDeCharges:
    """
    Classe d'objet permettant de calculer les charges de copropriété en fonction des lots, des prestations et des provisions.
    """
    def __init__(self,LstLot:  List[Lot], LstPrestationsSelectionnees: List[Prestation], LstProvisions: List[Provision]):
        self.Lots = LstLot
        self.Prestations = LstPrestationsSelectionnees
        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Postes de provisions': [provision.Nom for provision in LstProvisions],
            'Tantiemes': 0,
            'Provisions':[provision.Provision for provision in LstProvisions]
        }
        self.DfCharges= pd.DataFrame(tableauTantiemesInitialise)

        #Incrémenter les tantièmes dans le tableau des charges
        for provision in LstProvisions:
            for lot in LstLot:
                #On récupère les tantièmes du lot pour le poste de provision
                tantiemesLot = lot.DfTantiemes.loc[lot.DfTantiemes['ID des subdivisions'] == provision.ID, 'Tantiemes'].values[0]
                #On l'ajoute dans le tableau des charges
                self.DfCharges.loc[self.DfCharges['Postes de provisions'] == provision.Nom, 'Tantiemes'] += tantiemesLot

    def Etape1ConstruireTableauDeCharges (self):
        """
        Méthode permettant de calculer les charges totales de copropriété en fonction des prestations et des provisions.
        """

        #Itération pour calculer les charges totales
        for provision in self.Provisions:
            CoutReelDuPosteDeProvision = 0
            #Pour chaque provision on checke si on a des prestations associées
            for prestation in self.Prestations:
                #S'il y a des prestations associées à la provision, on ajoute le coût de la prestation aux charges totales et on enlève les provisions
                if prestation.IDPosteDeProvision == provision.IDPosteDeProvision:
                    CoutReelDuPosteDeProvision += prestation.Cout
        
            if CoutReelDuPosteDeProvision==0:
                CoutReelDuPosteDeProvision=provision.Cout
            self.ChargesTotales += CoutReelDuPosteDeProvision


    def Etape2CalculerLesChargesParLot (self):
        """
        Méthode permettant de calculer les charges par lot en fonction des tantièmes et des charges totales.
        """
        #Pour chaque tantièmes on calcul les couts
        for lot in self.Lots:
            totalTantiemes = lot.DfTantiemes['Tantiemes'].sum()
            chargesLot = 0
            for index, row in lot.DfTantiemes.iterrows():
                chargesLot += (row['Tantiemes'] / totalTantiemes) * self.ChargesTotales
            self.ChargesParLot[lot.IDNotaire] = chargesLot
        return self.ChargesParLot


#
# Début de l'affiche du site web #
# 

# Titre de l'application
st.title("Calculateur de charges de copropriété")

# Un sous-titre
st.subheader("Ce calculateur permet d'estimer les charges de copropriété en fonction des prestations sélectionnées et des tantièmes des lots choisis")

# Un widget interactif : une boîte de saisie de texte
nom = st.text_input("Quel est votre nom ?")

# Une condition pour afficher un message si le texte est rempli
if nom:
    st.write(f"Bonjour {nom} ! Ravi de vous rencontrer.")

# Un slider interactif
age = st.slider("Sélectionnez votre âge", 0, 100, 25)
st.write(f"Vous avez {age} ans.")